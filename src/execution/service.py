import uuid

from src.core.enums import RecordStatus, UserAction
from src.storage.service import StorageService


class ExecutionService:
    def __init__(self, storage: StorageService):
        self.storage = storage

    def execute(self, record_id: uuid.UUID, action: UserAction) -> dict:
        if action == UserAction.APPROVE:
            success = self.storage.update_status(record_id, RecordStatus.APPROVED)
            return {
                "record_id": str(record_id),
                "action": action.value,
                "new_status": RecordStatus.APPROVED.value,
                "success": success,
            }

        if action == UserAction.REJECT:
            success = self.storage.update_status(record_id, RecordStatus.REJECTED)
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
