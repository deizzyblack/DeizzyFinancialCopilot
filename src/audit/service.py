import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from src.core.schemas import AuditEntry
from src.models.database import AuditLog


class AuditService:
    def __init__(self, session: Session):
        self.session = session

    def log(
        self,
        event_type: str,
        file_id: uuid.UUID | None = None,
        record_id: uuid.UUID | None = None,
        actor: str = "system",
        details: dict[str, Any] | None = None,
    ) -> AuditEntry:
        row = AuditLog(
            id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.now(UTC),
            file_id=str(file_id) if file_id else None,
            record_id=str(record_id) if record_id else None,
            actor=actor,
            details_json=json.dumps(details or {}, default=str),
        )
        self.session.add(row)
        self.session.flush()

        return AuditEntry(
            event_type=row.event_type,
            timestamp=row.timestamp,
            file_id=uuid.UUID(row.file_id) if row.file_id else None,
            record_id=uuid.UUID(row.record_id) if row.record_id else None,
            actor=row.actor,
            details=details or {},
        )

    def get_log(
        self,
        file_id: uuid.UUID | None = None,
        record_id: uuid.UUID | None = None,
        event_type: str | None = None,
    ) -> list[AuditEntry]:
        query = self.session.query(AuditLog)

        if file_id:
            query = query.filter(AuditLog.file_id == str(file_id))
        if record_id:
            query = query.filter(AuditLog.record_id == str(record_id))
        if event_type:
            query = query.filter(AuditLog.event_type == event_type)

        query = query.order_by(AuditLog.timestamp.asc())
        rows = query.all()

        return [self._row_to_entry(r) for r in rows]

    def get_full_log(self) -> list[AuditEntry]:
        rows = (
            self.session.query(AuditLog)
            .order_by(AuditLog.timestamp.asc())
            .all()
        )
        return [self._row_to_entry(r) for r in rows]

    def _row_to_entry(self, row: AuditLog) -> AuditEntry:
        return AuditEntry(
            event_type=row.event_type,
            timestamp=row.timestamp,
            file_id=uuid.UUID(row.file_id) if row.file_id else None,
            record_id=uuid.UUID(row.record_id) if row.record_id else None,
            actor=row.actor,
            details=row.details,
        )
