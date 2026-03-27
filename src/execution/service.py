import uuid

from src.core.enums import RecordStatus, StandardMetric, UserAction
from src.mapping.service import SemanticMapper
from src.storage.service import StorageService


class ExecutionService:
    def __init__(self, storage: StorageService, mapper: SemanticMapper | None = None):
        self.storage = storage
        self.mapper = mapper

    def execute(self, record_id: uuid.UUID, action: UserAction) -> dict:
        if action == UserAction.APPROVE:
            success = self.storage.update_status(record_id, RecordStatus.APPROVED)
            if success and self.mapper:
                self._learn_approval(record_id)
            return {
                "record_id": str(record_id),
                "action": action.value,
                "new_status": RecordStatus.APPROVED.value,
                "success": success,
            }

        if action == UserAction.REJECT:
            success = self.storage.update_status(record_id, RecordStatus.REJECTED)
            if success and self.mapper:
                self._learn_rejection(record_id)
            return {
                "record_id": str(record_id),
                "action": action.value,
                "new_status": RecordStatus.REJECTED.value,
                "success": success,
            }

        return {
            "record_id": str(record_id),
            "action": action.value,
            "new_status": RecordStatus.PENDING.value,
            "success": True,
            "note": "Marked for investigation — status unchanged",
        }

    def _learn_approval(self, record_id: uuid.UUID) -> None:
        """Feed approved mapping back into mapping memory."""
        from src.models.database import FinancialRecord

        row = self.storage.session.query(FinancialRecord).filter(
            FinancialRecord.id == str(record_id)
        ).first()
        if not row or not row.raw_label or not row.metric:
            return

        try:
            metric = StandardMetric(row.metric)
        except ValueError:
            return

        self.mapper.add_company_mapping(row.company_id, row.raw_label, metric)

    def _learn_rejection(self, record_id: uuid.UUID) -> None:
        """Record rejected mapping as negative signal."""
        from src.models.database import FinancialRecord

        row = self.storage.session.query(FinancialRecord).filter(
            FinancialRecord.id == str(record_id)
        ).first()
        if not row or not row.raw_label or not row.metric:
            return

        try:
            metric = StandardMetric(row.metric)
        except ValueError:
            return

        self.mapper.reject_mapping(row.company_id, row.raw_label, metric)
