import uuid
from datetime import datetime, timezone

from src.core.enums import RecordStatus
from src.core.schemas import CandidateRecord


class StorageRecord:
    def __init__(self, record_id: uuid.UUID, record: CandidateRecord, created_at: datetime):
        self.record_id = record_id
        self.record = record
        self.created_at = created_at
        self.status = record.status
        self.version = 1


class StorageService:
    """In-memory append-only storage. Replace with PostgreSQL in production."""

    def __init__(self):
        self._records: list[StorageRecord] = []

    def store(self, record: CandidateRecord) -> StorageRecord:
        stored = StorageRecord(
            record_id=uuid.uuid4(),
            record=record,
            created_at=datetime.now(timezone.utc),
        )
        self._records.append(stored)
        return stored

    def get_latest_approved(
        self, company_id: str, metric: str, period: str
    ) -> StorageRecord | None:
        matches = [
            r
            for r in self._records
            if r.record.company_id == company_id
            and r.record.metric.value == metric
            and r.record.period == period
            and r.status == RecordStatus.APPROVED
        ]
        if not matches:
            return None
        return max(matches, key=lambda r: r.created_at)

    def get_revision_count(self, company_id: str, metric: str, period: str) -> int:
        return len(
            [
                r
                for r in self._records
                if r.record.company_id == company_id
                and r.record.metric.value == metric
                and r.record.period == period
            ]
        )

    def update_status(self, record_id: uuid.UUID, status: RecordStatus) -> bool:
        for r in self._records:
            if r.record_id == record_id:
                r.status = status
                return True
        return False

    def get_all_pending(self) -> list[StorageRecord]:
        return [r for r in self._records if r.status == RecordStatus.PENDING]

    def get_records_by_file(self, file_id: uuid.UUID) -> list[StorageRecord]:
        return [r for r in self._records if r.record.file_id == file_id]

    def get_records_for_period(
        self, company_id: str, period: str
    ) -> list[StorageRecord]:
        return [
            r
            for r in self._records
            if r.record.company_id == company_id and r.record.period == period
        ]
