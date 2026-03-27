import uuid
from pathlib import Path

from src.action.service import ActionGenerator
from src.audit.service import AuditService
from src.change_detection.service import ChangeDetectionService
from src.confidence.service import ConfidenceEngine
from src.core.enums import AuditEventType, FileStatus
from src.core.schemas import ActionRecommendation, PipelineResult
from src.decision.service import DecisionEngine
from src.ingestion.service import IngestionService
from src.mapping.service import SemanticMapper
from src.normalization.service import NormalizationService
from src.parser.service import DocumentParser
from src.period.service import PeriodNormalizer
from src.sanity.service import SanityEngine
from src.source_reliability.service import SourceReliabilityService
from src.storage.service import StorageService


class Pipeline:
    def __init__(self):
        self.ingestion = IngestionService()
        self.parser = DocumentParser()
        self.mapper = SemanticMapper()
        self.period_normalizer = PeriodNormalizer()
        self.normalizer = NormalizationService()
        self.storage = StorageService()
        self.change_detector = ChangeDetectionService(self.storage)
        self.sanity = SanityEngine(self.storage)
        self.source_reliability = SourceReliabilityService()
        self.confidence = ConfidenceEngine()
        self.decision = DecisionEngine()
        self.action_generator = ActionGenerator()
        self.audit = AuditService()

    def process_file(
        self,
        file_path: Path,
        company_id: str,
        uploaded_by: str = "system",
        source_type: str = "manual_upload",
    ) -> PipelineResult:
        errors = []
        actions: list[ActionRecommendation] = []

        # M1 — Ingest
        file_meta = self.ingestion.ingest_file(file_path, uploaded_by)
        self.audit.log(
            AuditEventType.FILE_INGESTED.value,
            file_id=file_meta.file_id,
            details={"filename": file_meta.filename, "status": file_meta.status.value},
        )

        if file_meta.status == FileStatus.DUPLICATE:
            self.audit.log(
                AuditEventType.FILE_DUPLICATE.value,
                file_id=file_meta.file_id,
                details={"hash": file_meta.file_hash},
            )
            return PipelineResult(
                file_id=file_meta.file_id,
                status="DUPLICATE",
            )

        # M2 — Parse
        stored_path = self.ingestion.get_stored_path(file_meta.file_id, file_meta.filename)
        try:
            extractions = self.parser.parse_excel(stored_path)
        except Exception as e:
            errors.append(f"Parse error: {e}")
            return PipelineResult(
                file_id=file_meta.file_id,
                status="FAILED",
                errors=errors,
            )

        self.audit.log(
            AuditEventType.DATA_PARSED.value,
            file_id=file_meta.file_id,
            details={"records_extracted": len(extractions)},
        )

        records_created = 0
        source_score = self.source_reliability.get_score(source_type, uploaded_by)

        for extraction in extractions:
            # M3 — Map
            mapping = self.mapper.map_label(extraction.raw_label, company_id)
            if mapping.metric is None:
                continue

            self.audit.log(
                AuditEventType.METRIC_MAPPED.value,
                file_id=file_meta.file_id,
                details={
                    "raw_label": extraction.raw_label,
                    "metric": mapping.metric.value if mapping.metric else None,
                    "method": mapping.method.value,
                    "score": mapping.mapping_score,
                },
            )

            # M4 — Period
            period_raw = extraction.column_header or ""
            period = self.period_normalizer.normalize(period_raw)

            self.audit.log(
                AuditEventType.PERIOD_NORMALIZED.value,
                file_id=file_meta.file_id,
                details={
                    "raw": period.raw_period,
                    "normalized": period.normalized_period,
                    "type": period.period_type.value,
                },
            )

            # M5 — Normalize
            record = self.normalizer.normalize(
                extraction, mapping, period, company_id, file_meta.file_id
            )
            if record is None:
                continue

            # M6 — Store
            stored = self.storage.store(record)
            records_created += 1

            self.audit.log(
                AuditEventType.RECORD_CREATED.value,
                file_id=file_meta.file_id,
                record_id=stored.record_id,
                details={"metric": record.metric.value, "value": record.value},
            )

            # M7 — Change Detection
            change = self.change_detector.detect(record)
            self.audit.log(
                AuditEventType.CHANGE_DETECTED.value,
                file_id=file_meta.file_id,
                record_id=stored.record_id,
                details={"type": change.change_type.value},
            )

            # M8 — Sanity
            sanity_result = self.sanity.check(record)
            self.audit.log(
                AuditEventType.SANITY_CHECK.value,
                file_id=file_meta.file_id,
                record_id=stored.record_id,
                details={"passed": sanity_result.passed, "issues": sanity_result.issues},
            )

            # M10 — Confidence
            conf = self.confidence.score(
                record, mapping, period, sanity_result, source_score, change
            )
            self.audit.log(
                AuditEventType.CONFIDENCE_SCORED.value,
                file_id=file_meta.file_id,
                record_id=stored.record_id,
                details={"total": conf.total, "blocked": conf.hard_blocked},
            )

            # M11 — Decision
            decision = self.decision.decide(conf)
            self.audit.log(
                AuditEventType.DECISION_MADE.value,
                file_id=file_meta.file_id,
                record_id=stored.record_id,
                details={"decision": decision.decision.value, "reason": decision.reason},
            )

            # M12 — Action
            action = self.action_generator.generate(decision, change, stored.record_id)
            actions.append(action)
            self.audit.log(
                AuditEventType.ACTION_GENERATED.value,
                file_id=file_meta.file_id,
                record_id=stored.record_id,
                details={"action": action.action.value, "reason": action.reason},
            )

        return PipelineResult(
            file_id=file_meta.file_id,
            status="COMPLETED",
            records_extracted=len(extractions),
            records_created=records_created,
            actions=actions,
            errors=errors,
        )
