import json
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

    def get_by_id(self, record_id: uuid.UUID) -> StorageRecord | None:
        row = (
            self.session.query(FinancialRecord)
            .filter(FinancialRecord.id == str(record_id))
            .first()
        )
        return StorageRecord(row) if row else None

    def update_pipeline_metadata(
        self,
        record_id: uuid.UUID,
        *,
        mapping_method: str | None = None,
        mapping_reason: str | None = None,
        raw_period: str | None = None,
        confidence_total: float | None = None,
        confidence_extraction: float | None = None,
        confidence_mapping: float | None = None,
        confidence_sanity: float | None = None,
        confidence_source: float | None = None,
        confidence_historical: float | None = None,
        decision: str | None = None,
        decision_reason: str | None = None,
        sanity_passed: bool | None = None,
        sanity_issues: list[str] | None = None,
        change_type: str | None = None,
        previous_value: float | None = None,
        source_filename: str | None = None,
    ) -> None:
        row = (
            self.session.query(FinancialRecord)
            .filter(FinancialRecord.id == str(record_id))
            .first()
        )
        if not row:
            return

        if mapping_method is not None:
            row.mapping_method = mapping_method
        if mapping_reason is not None:
            row.mapping_reason = mapping_reason
        if raw_period is not None:
            row.raw_period = raw_period
        if confidence_total is not None:
            row.confidence_total = confidence_total
        if confidence_extraction is not None:
            row.confidence_extraction = confidence_extraction
        if confidence_mapping is not None:
            row.confidence_mapping = confidence_mapping
        if confidence_sanity is not None:
            row.confidence_sanity = confidence_sanity
        if confidence_source is not None:
            row.confidence_source = confidence_source
        if confidence_historical is not None:
            row.confidence_historical = confidence_historical
        if decision is not None:
            row.decision = decision
        if decision_reason is not None:
            row.decision_reason = decision_reason
        if sanity_passed is not None:
            row.sanity_passed = "true" if sanity_passed else "false"
        if sanity_issues is not None:
            row.sanity_issues_json = json.dumps(sanity_issues)
        if change_type is not None:
            row.change_type = change_type
        if previous_value is not None:
            row.previous_value = previous_value
        if source_filename is not None:
            row.source_filename = source_filename

        self.session.flush()

    def get_pending_filtered(
        self,
        decision_filter: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[StorageRecord], int]:
        query = self.session.query(FinancialRecord).filter(
            FinancialRecord.status == RecordStatus.PENDING.value
        )
        if decision_filter:
            query = query.filter(FinancialRecord.decision == decision_filter)

        total = query.count()
        rows = (
            query.order_by(FinancialRecord.confidence_total.asc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return [StorageRecord(r) for r in rows], total

    def _next_version(self, company_id: str, metric: str, period: str) -> int:
        count = self.get_revision_count(company_id, metric, period)
        return count + 1
