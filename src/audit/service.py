import uuid
from datetime import datetime, timezone
from typing import Any

from src.core.schemas import AuditEntry


class AuditService:
    def __init__(self):
        self._log: list[AuditEntry] = []

    def log(
        self,
        event_type: str,
        file_id: uuid.UUID | None = None,
        record_id: uuid.UUID | None = None,
        actor: str = "system",
        details: dict[str, Any] | None = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            file_id=file_id,
            record_id=record_id,
            actor=actor,
            details=details or {},
        )
        self._log.append(entry)
        return entry

    def get_log(
        self,
        file_id: uuid.UUID | None = None,
        record_id: uuid.UUID | None = None,
        event_type: str | None = None,
    ) -> list[AuditEntry]:
        results = self._log

        if file_id:
            results = [e for e in results if e.file_id == file_id]
        if record_id:
            results = [e for e in results if e.record_id == record_id]
        if event_type:
            results = [e for e in results if e.event_type == event_type]

        return results

    def get_full_log(self) -> list[AuditEntry]:
        return list(self._log)
