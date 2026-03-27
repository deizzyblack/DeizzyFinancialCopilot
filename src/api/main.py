import shutil
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from src.api.pipeline import Pipeline
from src.core.enums import UserAction
from src.core.schemas import PipelineResult
from src.execution.service import ExecutionService
from src.models.database import Base, get_engine, get_session_factory

app = FastAPI(
    title="Financial Data Autopilot",
    description="Ingests, validates, and acts on financial data with controlled automation",
    version="0.1.0",
)

engine = get_engine()
Base.metadata.create_all(engine)
SessionFactory = get_session_factory()


def get_db() -> Session:
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


@app.get("/health")
def health():
    return {"status": "ok", "service": "Financial Data Autopilot"}


@app.post("/ingest", response_model=PipelineResult)
async def ingest_file(
    file: UploadFile = File(...),
    company_id: str = Query(..., description="Company identifier"),
    uploaded_by: str = Query(default="system", description="Uploader identity"),
    source_type: str = Query(default="manual_upload", description="Source type"),
    db: Session = Depends(get_db),
):
    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        pipeline = Pipeline(db)
        result = pipeline.process_file(
            file_path=tmp_path,
            company_id=company_id,
            uploaded_by=uploaded_by,
            source_type=source_type,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    return result


@app.post("/execute/{record_id}")
def execute_action(
    record_id: UUID,
    action: UserAction = Query(..., description="User action: APPROVE, REJECT, INVESTIGATE"),
    db: Session = Depends(get_db),
):
    from src.audit.service import AuditService
    from src.storage.service import StorageService

    storage = StorageService(db)
    execution = ExecutionService(storage)
    audit = AuditService(db)

    result = execution.execute(record_id, action)
    if not result["success"]:
        raise HTTPException(status_code=404, detail="Record not found")

    audit.log(
        "USER_ACTION",
        record_id=record_id,
        details={"action": action.value, "result": result},
    )
    db.commit()

    return result


@app.get("/records/pending")
def get_pending_records(db: Session = Depends(get_db)):
    from src.storage.service import StorageService

    storage = StorageService(db)
    records = storage.get_all_pending()
    return [
        {
            "record_id": str(r.record_id),
            "company_id": r.record.company_id,
            "metric": r.record.metric.value,
            "value": r.record.value,
            "period": r.record.period,
            "status": r.status.value,
            "version": r.version,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]


@app.get("/audit")
def get_audit_log(
    file_id: UUID | None = None,
    record_id: UUID | None = None,
    event_type: str | None = None,
    db: Session = Depends(get_db),
):
    from src.audit.service import AuditService

    audit = AuditService(db)
    entries = audit.get_log(file_id, record_id, event_type)
    return [
        {
            "event_type": e.event_type,
            "timestamp": e.timestamp.isoformat(),
            "file_id": str(e.file_id) if e.file_id else None,
            "record_id": str(e.record_id) if e.record_id else None,
            "actor": e.actor,
            "details": e.details,
        }
        for e in entries
    ]
