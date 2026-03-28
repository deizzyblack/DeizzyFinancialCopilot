from pathlib import Path

from sqlalchemy.orm import Session

from src.action.service import ActionGenerator
from src.audit.service import AuditService
from src.change_detection.service import ChangeDetectionService
from src.confidence.service import ConfidenceEngine
from src.core.enums import AuditEventType, FileStatus
from src.core.schemas import ActionRecommendation, PipelineResult, RecordOutcome
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
    def __init__(self, session: Session, upload_dir: str | None = None):
        self.session = session
        self.ingestion = IngestionService(session, upload_dir=upload_dir)
        self.parser = DocumentParser()
        self.mapper = SemanticMapper(session)
        self.period_normalizer = PeriodNormalizer()
        self.normalizer = NormalizationService()
        self.storage = StorageService(session)
        self.change_detector = ChangeDetectionService(self.storage)
        self.sanity = SanityEngine(self.storage)
        self.source_reliability = SourceReliabilityService()
        self.confidence = ConfidenceEngine()
        self.decision = DecisionEngine()
        self.action_generator = ActionGenerator()
        self.audit = AuditService(session)

    def process_file(
        self,
        file_path: Path,
        company_id: str,
        uploaded_by: str = "system",
        source_type: str = "manual_upload",
    ) -> PipelineResult:
        errors = []
        actions: list[ActionRecommendation] = []
        outcomes: list[RecordOutcome] = []

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
            self.session.commit()
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
            self.session.commit()
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
        unmapped_count = 0
        source_score = self.source_reliability.get_score(source_type, uploaded_by)

        for extraction in extractions:
            # M3 — Map
            mapping = self.mapper.map_label(extraction.raw_label, company_id)
            if mapping.metric is None:
                unmapped_count += 1
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

            # Persist pipeline metadata on the record
            self.storage.update_pipeline_metadata(
                stored.record_id,
                mapping_method=mapping.method.value,
                mapping_reason=mapping.reason,
                raw_period=period.raw_period,
                confidence_total=conf.total,
                confidence_extraction=conf.extraction,
                confidence_mapping=conf.mapping,
                confidence_sanity=conf.sanity,
                confidence_source=conf.source,
                confidence_historical=conf.historical,
                decision=decision.decision.value,
                decision_reason=decision.reason,
                sanity_passed=sanity_result.passed,
                sanity_issues=sanity_result.issues,
                change_type=change.change_type.value,
                previous_value=change.old_value,
                source_filename=file_meta.filename,
            )

            outcomes.append(
                RecordOutcome(
                    record_id=stored.record_id,
                    metric=record.metric.value if record.metric else None,
                    value=record.value,
                    period=record.period,
                    confidence=conf.total,
                    decision=decision.decision.value,
                    reason=decision.reason,
                )
            )

        noise_filtered = self.parser.skipped_zero + self.parser.skipped_adj

        self.audit.log(
            AuditEventType.PIPELINE_COMPLETE.value,
            file_id=file_meta.file_id,
            details={
                "records_extracted": len(extractions),
                "records_created": records_created,
                "unmapped_count": unmapped_count,
                "noise_filtered_count": noise_filtered,
                "company_id": company_id,
            },
        )

        self.session.commit()

        return PipelineResult(
            file_id=file_meta.file_id,
            filename=file_meta.filename,
            status="COMPLETED",
            records_extracted=len(extractions),
            records_created=records_created,
            unmapped_count=unmapped_count,
            noise_filtered_count=noise_filtered,
            outcomes=outcomes,
            actions=actions,
            errors=errors,
        )
