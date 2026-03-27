"""Tests for the learning loop: user APPROVE/REJECT → mapping memory feedback."""

import uuid

from src.core.enums import (
    MappingMethod,
    PeriodType,
    StandardMetric,
    UserAction,
)
from src.core.schemas import CandidateRecord
from src.execution.service import ExecutionService
from src.mapping.service import SemanticMapper
from src.models.database import MappingMemory
from src.storage.service import StorageService


def _store_record(
    storage: StorageService,
    raw_label: str = "Net Sales",
    metric: StandardMetric = StandardMetric.REVENUE,
    company_id: str = "ACME",
):
    """Helper: store a financial record and return its StorageRecord."""
    record = CandidateRecord(
        company_id=company_id,
        metric=metric,
        value=1000000.0,
        raw_label=raw_label,
        period="Q2-2025",
        period_type=PeriodType.QUARTER,
        file_id=uuid.uuid4(),
        sheet="Sheet1",
        cell="B2",
        mapping_score=0.95,
    )
    return storage.store(record)


class TestLearningOnApproval:
    def test_approve_creates_mapping_memory(self, db_session):
        """APPROVE should insert a company-approved mapping."""
        storage = StorageService(db_session)
        mapper = SemanticMapper(db_session)
        execution = ExecutionService(storage, mapper)

        stored = _store_record(storage, raw_label="Umsatz")
        execution.execute(stored.record_id, UserAction.APPROVE)

        row = (
            db_session.query(MappingMemory)
            .filter(
                MappingMemory.company_id == "ACME",
                MappingMemory.original_label == "umsatz",
            )
            .first()
        )
        assert row is not None
        assert row.approved == "true"
        assert row.mapped_metric == "Revenue"
        assert row.approve_count == 1

    def test_approve_increments_count(self, db_session):
        """Multiple approvals of the same label→metric should increment."""
        storage = StorageService(db_session)
        mapper = SemanticMapper(db_session)
        execution = ExecutionService(storage, mapper)

        s1 = _store_record(storage, raw_label="Umsatz")
        execution.execute(s1.record_id, UserAction.APPROVE)

        s2 = _store_record(storage, raw_label="Umsatz")
        execution.execute(s2.record_id, UserAction.APPROVE)

        row = (
            db_session.query(MappingMemory)
            .filter(
                MappingMemory.company_id == "ACME",
                MappingMemory.original_label == "umsatz",
                MappingMemory.mapped_metric == "Revenue",
            )
            .first()
        )
        assert row.approve_count == 2

    def test_approved_mapping_used_in_future(self, db_session):
        """After approval, the mapper should use the learned mapping."""
        storage = StorageService(db_session)
        mapper = SemanticMapper(db_session)
        execution = ExecutionService(storage, mapper)

        stored = _store_record(storage, raw_label="Umsatz")
        execution.execute(stored.record_id, UserAction.APPROVE)

        result = mapper.map_label("Umsatz", company_id="ACME")
        assert result.metric == StandardMetric.REVENUE
        assert result.method == MappingMethod.COMPANY_APPROVED
        assert result.mapping_score >= 0.95

    def test_approval_score_increases_with_count(self, db_session):
        """3+ approvals should give maximum score of 1.0."""
        storage = StorageService(db_session)
        mapper = SemanticMapper(db_session)
        execution = ExecutionService(storage, mapper)

        for _ in range(3):
            stored = _store_record(storage, raw_label="Umsatz")
            execution.execute(stored.record_id, UserAction.APPROVE)

        result = mapper.map_label("Umsatz", company_id="ACME")
        assert result.mapping_score == 1.0


class TestLearningOnRejection:
    def test_reject_creates_negative_signal(self, db_session):
        """REJECT should store a rejected mapping entry."""
        storage = StorageService(db_session)
        mapper = SemanticMapper(db_session)
        execution = ExecutionService(storage, mapper)

        stored = _store_record(storage, raw_label="Umsatz")
        execution.execute(stored.record_id, UserAction.REJECT)

        row = (
            db_session.query(MappingMemory)
            .filter(
                MappingMemory.company_id == "ACME",
                MappingMemory.original_label == "umsatz",
            )
            .first()
        )
        assert row is not None
        assert row.approved == "rejected"
        assert row.reject_count == 1

    def test_rejected_mapping_skipped_in_future(self, db_session):
        """A rejected mapping should not be returned by map_label."""
        storage = StorageService(db_session)
        mapper = SemanticMapper(db_session)
        execution = ExecutionService(storage, mapper)

        # First approve to create a company mapping
        s1 = _store_record(storage, raw_label="Umsatz")
        execution.execute(s1.record_id, UserAction.APPROVE)

        # Then reject it — should flip to rejected
        s2 = _store_record(storage, raw_label="Umsatz")
        execution.execute(s2.record_id, UserAction.REJECT)

        # map_label should now fall through to rule-based (Umsatz has no synonym)
        result = mapper.map_label("Umsatz", company_id="ACME")
        assert result.method == MappingMethod.RULE_BASED
        assert result.metric is None  # Umsatz is not in SYNONYM_MAP

    def test_reject_increments_count(self, db_session):
        """Multiple rejections should increment reject_count."""
        storage = StorageService(db_session)
        mapper = SemanticMapper(db_session)
        execution = ExecutionService(storage, mapper)

        s1 = _store_record(storage, raw_label="Umsatz")
        execution.execute(s1.record_id, UserAction.REJECT)

        s2 = _store_record(storage, raw_label="Umsatz")
        execution.execute(s2.record_id, UserAction.REJECT)

        row = (
            db_session.query(MappingMemory)
            .filter(
                MappingMemory.company_id == "ACME",
                MappingMemory.original_label == "umsatz",
            )
            .first()
        )
        assert row.reject_count == 2


class TestLearningEdgeCases:
    def test_investigate_does_not_learn(self, db_session):
        """INVESTIGATE should not create any mapping memory."""
        storage = StorageService(db_session)
        mapper = SemanticMapper(db_session)
        execution = ExecutionService(storage, mapper)

        stored = _store_record(storage, raw_label="Umsatz")
        execution.execute(stored.record_id, UserAction.INVESTIGATE)

        count = db_session.query(MappingMemory).count()
        assert count == 0

    def test_no_mapper_still_works(self, db_session):
        """ExecutionService without mapper should still approve/reject."""
        storage = StorageService(db_session)
        execution = ExecutionService(storage, mapper=None)

        stored = _store_record(storage, raw_label="Umsatz")
        result = execution.execute(stored.record_id, UserAction.APPROVE)

        assert result["success"] is True
        assert result["new_status"] == "APPROVED"

    def test_approve_then_reject_flips_status(self, db_session):
        """Rejecting after approval should flip mapping to rejected."""
        storage = StorageService(db_session)
        mapper = SemanticMapper(db_session)
        execution = ExecutionService(storage, mapper)

        s1 = _store_record(storage, raw_label="Umsatz")
        execution.execute(s1.record_id, UserAction.APPROVE)

        s2 = _store_record(storage, raw_label="Umsatz")
        execution.execute(s2.record_id, UserAction.REJECT)

        row = (
            db_session.query(MappingMemory)
            .filter(
                MappingMemory.company_id == "ACME",
                MappingMemory.original_label == "umsatz",
                MappingMemory.mapped_metric == "Revenue",
            )
            .first()
        )
        assert row.approved == "rejected"
        assert row.approve_count == 1
        assert row.reject_count == 1

    def test_learning_is_per_company(self, db_session):
        """Approving for ACME should not affect BETA's mappings."""
        storage = StorageService(db_session)
        mapper = SemanticMapper(db_session)
        execution = ExecutionService(storage, mapper)

        stored = _store_record(storage, raw_label="Umsatz", company_id="ACME")
        execution.execute(stored.record_id, UserAction.APPROVE)

        result_acme = mapper.map_label("Umsatz", company_id="ACME")
        result_beta = mapper.map_label("Umsatz", company_id="BETA")

        assert result_acme.method == MappingMethod.COMPANY_APPROVED
        assert result_beta.method == MappingMethod.RULE_BASED

    def test_rule_boost_from_prior_approval(self, db_session):
        """Approved mappings should boost rule-based scores for same label."""
        storage = StorageService(db_session)
        mapper = SemanticMapper(db_session)
        execution = ExecutionService(storage, mapper)

        # Approve a "revenue" record (which is also in SYNONYM_MAP)
        stored = _store_record(
            storage, raw_label="revenue", metric=StandardMetric.REVENUE
        )
        execution.execute(stored.record_id, UserAction.APPROVE)

        # Now map_label for "revenue" with company_id should get the
        # company-approved path directly
        result = mapper.map_label("revenue", company_id="ACME")
        assert result.method == MappingMethod.COMPANY_APPROVED

    def test_audit_preserved_on_learning(self, db_session):
        """Learning actions should not interfere with append-only audit."""
        from src.models.database import FinancialRecord

        storage = StorageService(db_session)
        mapper = SemanticMapper(db_session)
        execution = ExecutionService(storage, mapper)

        stored = _store_record(storage, raw_label="Umsatz")
        execution.execute(stored.record_id, UserAction.APPROVE)

        # Original record still exists, status changed
        row = db_session.query(FinancialRecord).filter(
            FinancialRecord.id == str(stored.record_id)
        ).first()
        assert row.status == "APPROVED"
        assert row.raw_label == "Umsatz"  # unchanged
        assert row.value == 1000000.0  # unchanged
