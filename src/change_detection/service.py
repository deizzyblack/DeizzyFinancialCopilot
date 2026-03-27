from src.core.enums import ChangeType
from src.core.schemas import CandidateRecord, ChangeDetectionResult
from src.storage.service import StorageService


class ChangeDetectionService:
    def __init__(self, storage: StorageService):
        self.storage = storage

    def detect(self, record: CandidateRecord) -> ChangeDetectionResult:
        latest = self.storage.get_latest_approved(
            company_id=record.company_id,
            metric=record.metric.value,
            period=record.period,
        )

        revision_count = self.storage.get_revision_count(
            company_id=record.company_id,
            metric=record.metric.value,
            period=record.period,
        )

        if latest is None:
            return ChangeDetectionResult(
                change_type=ChangeType.NEW,
                new_value=record.value,
                revision_count=revision_count,
            )

        if latest.record.value == record.value:
            return ChangeDetectionResult(
                change_type=ChangeType.DUPLICATE,
                old_value=latest.record.value,
                new_value=record.value,
                diff=0.0,
                revision_count=revision_count,
            )

        return ChangeDetectionResult(
            change_type=ChangeType.REVISION,
            old_value=latest.record.value,
            new_value=record.value,
            diff=record.value - latest.record.value,
            revision_count=revision_count,
        )
