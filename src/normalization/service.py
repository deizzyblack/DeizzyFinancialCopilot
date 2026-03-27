import uuid

from src.core.enums import RecordStatus
from src.core.schemas import CandidateRecord, MappingResult, PeriodResult, RawExtraction


class NormalizationService:
    def normalize(
        self,
        extraction: RawExtraction,
        mapping: MappingResult,
        period: PeriodResult,
        company_id: str,
        file_id: uuid.UUID,
    ) -> CandidateRecord | None:
        if mapping.metric is None:
            return None

        value = extraction.raw_value
        if value is None:
            return None

        if isinstance(value, str):
            try:
                value = float(value.replace(",", "").strip())
            except ValueError:
                return None

        return CandidateRecord(
            company_id=company_id,
            metric=mapping.metric,
            value=float(value),
            raw_label=extraction.raw_label,
            period=period.normalized_period,
            period_type=period.period_type,
            file_id=file_id,
            sheet=extraction.sheet,
            cell=extraction.cell,
            status=RecordStatus.PENDING,
            mapping_score=mapping.mapping_score,
            period_confidence=period.confidence,
        )
