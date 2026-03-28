import json
import shutil
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from src.api.pipeline import Pipeline
from src.core.enums import UserAction
from src.core.schemas import PipelineResult
from src.execution.service import ExecutionService
from src.models.database import AuditLog, Base, get_engine, get_session_factory

app = FastAPI(
    title="Financial Data Autopilot",
    description="Ingests, validates, and acts on financial data with controlled automation",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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
    from src.mapping.service import SemanticMapper
    from src.storage.service import StorageService

    storage = StorageService(db)
    mapper = SemanticMapper(db)
    execution = ExecutionService(storage, mapper)
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
def get_pending_records(
    decision: str | None = Query(None, description="Filter: AUTO_READY, REVIEW_REQUIRED, FLAG"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    from src.storage.service import StorageService

    storage = StorageService(db)
    records, total = storage.get_pending_filtered(decision, page, per_page)

    return {
        "records": [
            {
                "record_id": str(r.record_id),
                "company_id": r.record.company_id,
                "metric": r.record.metric.value if r.record.metric else None,
                "value": r.record.value,
                "normalized_period": r.record.period,
                "confidence": r._row.confidence_total or 0.0,
                "decision": r._row.decision or "",
                "reason": r._row.decision_reason or "",
                "source_file": r._row.source_filename or "",
                "status": r.status.value,
                "version": r.version,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in records
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@app.get("/records/{record_id}")
def get_record_detail(
    record_id: UUID,
    db: Session = Depends(get_db),
):
    from src.storage.service import StorageService

    storage = StorageService(db)
    sr = storage.get_by_id(record_id)
    if not sr:
        raise HTTPException(status_code=404, detail="Record not found")

    row = sr._row
    sanity_issues = []
    if row.sanity_issues_json:
        try:
            sanity_issues = json.loads(row.sanity_issues_json)
        except (json.JSONDecodeError, TypeError):
            pass

    previous_value = row.previous_value
    delta = None
    delta_percent = None
    if previous_value is not None and row.value:
        delta = row.value - previous_value
        if previous_value != 0:
            delta_percent = round((delta / previous_value) * 100, 2)

    return {
        "record_id": str(sr.record_id),
        "company_id": row.company_id,
        "status": row.status,
        "version": row.version,
        # Data
        "metric": row.metric,
        "value": row.value,
        "normalized_period": row.period,
        # Source traceability
        "source_file": row.source_filename or "",
        "sheet_name": row.sheet or "",
        "cell_reference": row.cell or "",
        "raw_label": row.raw_label or "",
        "mapped_metric": row.metric,
        "mapping_method": row.mapping_method or "",
        "mapping_reason": row.mapping_reason or "",
        "raw_period": row.raw_period or "",
        "period_type": row.period_type or "",
        # Confidence
        "confidence_total": row.confidence_total or 0.0,
        "confidence_breakdown": {
            "extraction": row.confidence_extraction or 0.0,
            "mapping": row.confidence_mapping or 0.0,
            "sanity": row.confidence_sanity or 0.0,
            "source": row.confidence_source or 0.0,
            "historical": row.confidence_historical or 0.0,
        },
        # Sanity
        "sanity_passed": row.sanity_passed == "true" if row.sanity_passed else True,
        "sanity_issues": sanity_issues,
        # Change detection
        "change_type": row.change_type or "NEW",
        "previous_value": previous_value,
        "delta": delta,
        "delta_percent": delta_percent,
        # Decision
        "decision": row.decision or "",
        "decision_reason": row.decision_reason or "",
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


@app.get("/analysis/{company_id}")
def get_company_analysis(
    company_id: str,
    db: Session = Depends(get_db),
):
    """Company Analysis View — answers 4 questions about a company's financial data."""
    from dataclasses import asdict

    from src.analysis.service import CompanyAnalysisService

    service = CompanyAnalysisService(db)
    result = service.analyze(company_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No data found for company '{company_id}'")

    return asdict(result)


@app.get("/benchmarking")
def get_benchmarking(
    metric: str | None = Query(None, description="Filter by metric: Revenue, EBITDA, etc."),
    period: str | None = Query(None, description="Filter by period: Q3-2025, FY-2024, etc."),
    db: Session = Depends(get_db),
):
    """Cross-company metric comparison for portfolio monitoring."""
    from src.models.database import FinancialRecord

    query = db.query(FinancialRecord).filter(
        FinancialRecord.status == "APPROVED",
        FinancialRecord.metric.isnot(None),
    )

    if metric:
        query = query.filter(FinancialRecord.metric == metric)
    if period:
        query = query.filter(FinancialRecord.period == period)

    rows = query.order_by(FinancialRecord.company_id, FinancialRecord.period).all()

    # Group by company
    companies: dict[str, list] = {}
    for r in rows:
        if r.company_id not in companies:
            companies[r.company_id] = []
        companies[r.company_id].append({
            "metric": r.metric,
            "value": r.value,
            "period": r.period,
            "version": r.version,
            "confidence": r.confidence_total or 0.0,
        })

    # Compute summary stats per company
    summaries = []
    for company_id, records in companies.items():
        metrics_seen = set(r["metric"] for r in records)
        summaries.append({
            "company_id": company_id,
            "record_count": len(records),
            "metrics": sorted(metrics_seen),
            "records": records,
        })

    return {
        "companies": summaries,
        "total_companies": len(summaries),
        "filters": {"metric": metric, "period": period},
    }


@app.get("/audit")
def get_audit_log(
    file_id: UUID | None = None,
    record_id: UUID | None = None,
    event_type: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog)

    if file_id:
        query = query.filter(AuditLog.file_id == str(file_id))
    if record_id:
        query = query.filter(AuditLog.record_id == str(record_id))
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)

    total = query.count()
    rows = (
        query.order_by(AuditLog.timestamp.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "entries": [
            {
                "id": row.id,
                "event_type": row.event_type,
                "timestamp": row.timestamp.isoformat() if row.timestamp else "",
                "file_id": row.file_id,
                "record_id": row.record_id,
                "details": row.details,
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }
