import uuid

from src.confidence.service import ConfidenceEngine
from src.core.enums import (
    ChangeType,
    MappingMethod,
    PeriodType,
    StandardMetric,
)
from src.core.schemas import (
    CandidateRecord,
    ChangeDetectionResult,
    MappingResult,
    PeriodResult,
    SanityResult,
)


def _make_inputs(
    sanity_passed=True,
    mapping_score=0.95,
    period_confidence=0.9,
    source_score=0.7,
    change_type=ChangeType.NEW,
):
    record = CandidateRecord(
        company_id="ACME",
        metric=StandardMetric.REVENUE,
        value=1000000,
        raw_label="Revenue",
        period="Q2-2025",
        period_type=PeriodType.QUARTER,
        file_id=uuid.uuid4(),
        sheet="Sheet1",
        cell="B2",
    )
    mapping = MappingResult(
        metric=StandardMetric.REVENUE,
        mapping_score=mapping_score,
        method=MappingMethod.RULE_BASED,
        reason="test",
    )
    period = PeriodResult(
        raw_period="Q2 2025",
        normalized_period="Q2-2025",
        period_type=PeriodType.QUARTER,
        confidence=period_confidence,
    )
    sanity = SanityResult(
        passed=sanity_passed,
        issues=[] if sanity_passed else ["Balance sheet mismatch error"],
    )
    change = ChangeDetectionResult(change_type=change_type, new_value=1000000)
    return record, mapping, period, sanity, source_score, change


class TestConfidenceEngine:
    def test_high_confidence(self):
        engine = ConfidenceEngine()
        inputs = _make_inputs()
        score = engine.score(*inputs)
        assert score.total > 0.7
        assert not score.hard_blocked

    def test_sanity_failure_blocks(self):
        engine = ConfidenceEngine()
        inputs = _make_inputs(sanity_passed=False)
        score = engine.score(*inputs)
        assert score.hard_blocked
        assert len(score.block_reasons) > 0

    def test_low_mapping_reduces_score(self):
        engine = ConfidenceEngine()
        high = engine.score(*_make_inputs(mapping_score=0.95))
        low = engine.score(*_make_inputs(mapping_score=0.3))
        assert high.total > low.total

    def test_duplicate_high_historical(self):
        engine = ConfidenceEngine()
        inputs = _make_inputs(change_type=ChangeType.DUPLICATE)
        score = engine.score(*inputs)
        assert score.historical == 1.0
