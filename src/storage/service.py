import uuid
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.core.enums import RecordStatus, StandardMetric
from src.core.schemas import CandidateRecord
from src.models.database import FinancialRecord


class StorageRecord:
    """Thin wrapper that presents DB rows with the same interface downstream modules expect."""

    def __init__(self, db_row: FinancialRecord):
        self._row = db_row
        self.record_id = uuid.UUID(db_row.id)
        self.created_at = db_row.created_at
        self.status = RecordStatus(db_row.status)
        self.version = db_row.version

        self.record = CandidateRecord(
            company_id=db_row.company_id,
            metric=StandardMetric(db_row.metric),
            value=db_row.value,
            raw_label=db_row.raw_label or "",
            period=db_row.period,
            period_type=db_row.period_type,
            file_id=uuid.UUID(db_row.file_id),
            sheet=db_row.sheet or "",
            cell=db_row.cell or "",
            status=RecordStatus(db_row.status),
            mapping_score=db_row.mapping_score or 0.0,
            period_confidence=db_row.period_confidence or 0.0,
        )


class StorageService:
    """Append-only financial record storage backed by SQLAlchemy."""

    def __init__(self, session: Session):
        self.session = session

    def store(self, record: CandidateRecord) -> StorageRecord:
        version = self._next_version(
            record.company_id, record.metric.value, record.period
        )

        row = FinancialRecord(
            id=str(uuid.uuid4()),
            company_id=record.company_id,
            metric=record.metric.value,
            value=record.value,
            raw_label=record.raw_label,
            period=record.period,
            period_type=(
                record.period_type.value
                if hasattr(record.period_type, "value")
                else record.period_type
            ),
            file_id=str(record.file_id),
            sheet=record.sheet,
            cell=record.cell,
            status=record.status.value,
            mapping_score=record.mapping_score,
            period_confidence=record.period_confidence,
            version=version,
            created_at=datetime.now(UTC),
        )
        self.session.add(row)
        self.session.flush()
        return StorageRecord(row)

    def get_latest_approved(
        self, company_id: str, metric: str, period: str
    ) -> StorageRecord | None:
        row = (
            self.session.query(FinancialRecord)
            .filter(
                FinancialRecord.company_id == company_id,
                FinancialRecord.metric == metric,
                FinancialRecord.period == period,
                FinancialRecord.status == RecordStatus.APPROVED.value,
            )
            .order_by(FinancialRecord.created_at.desc())
            .first()
        )
        return StorageRecord(row) if row else None

    def get_revision_count(self, company_id: str, metric: str, period: str) -> int:
        return (
            self.session.query(func.count(FinancialRecord.id))
            .filter(
                FinancialRecord.company_id == company_id,
                FinancialRecord.metric == metric,
                FinancialRecord.period == period,
            )
            .scalar()
        )

    def update_status(self, record_id: uuid.UUID, status: RecordStatus) -> bool:
        row = self.session.query(FinancialRecord).filter(
            FinancialRecord.id == str(record_id)
        ).first()
        if row is None:
            return False
        row.status = status.value
        self.session.flush()
        return True

    def get_all_pending(self) -> list[StorageRecord]:
        rows = (
            self.session.query(FinancialRecord)
            .filter(FinancialRecord.status == RecordStatus.PENDING.value)
            .order_by(FinancialRecord.created_at.desc())
            .all()
        )
        return [StorageRecord(r) for r in rows]

    def get_records_by_file(self, file_id: uuid.UUID) -> list[StorageRecord]:
        rows = (
            self.session.query(FinancialRecord)
            .filter(FinancialRecord.file_id == str(file_id))
            .all()
        )
        return [StorageRecord(r) for r in rows]

    def get_records_for_period(
        self, company_id: str, period: str
    ) -> list[StorageRecord]:
        rows = (
            self.session.query(FinancialRecord)
            .filter(
                FinancialRecord.company_id == company_id,
                FinancialRecord.period == period,
            )
            .all()
        )
        return [StorageRecord(r) for r in rows]

    def _next_version(self, company_id: str, metric: str, period: str) -> int:
        count = self.get_revision_count(company_id, metric, period)
        return count + 1
