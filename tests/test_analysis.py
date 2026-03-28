"""Tests for the Company Analysis Service.

Covers:
- Company with single period (no comparison possible)
- Company with two periods + revision
- Missing core metrics detection (with type field)
- Anomaly surfacing with kind field — deduplication of sanity + hard_block
- Trust/confidence summary with label field + penalty
- Period chronological ordering
- Empty company returns None
"""

import json
import uuid
from datetime import UTC, datetime

from src.analysis.service import (
    CompanyAnalysisService,
    _trust_label,
    sort_periods,
)
from src.models.database import FinancialRecord

COMPANY = "test-corp"
FILE_ID = str(uuid.uuid4())


def _make_record(
    session,
    metric="Revenue",
    value=1000.0,
    period="Q1-2025",
    status="PENDING",
    confidence_total=0.75,
    decision="REVIEW_REQUIRED",
    decision_reason="",
    sanity_passed="true",
    sanity_issues_json="[]",
    mapping_method="rule_based",
    mapping_score=1.0,
    mapping_reason="Exact match",
    company_id=COMPANY,
    version=1,
):
    row = FinancialRecord(
        id=str(uuid.uuid4()),
        company_id=company_id,
        metric=metric,
        value=value,
        raw_label=metric,
        period=period,
        period_type="QUARTER",
        file_id=FILE_ID,
        sheet="Sheet1",
        cell="B2",
        status=status,
        mapping_score=mapping_score,
        mapping_method=mapping_method,
        mapping_reason=mapping_reason,
        confidence_total=confidence_total,
        decision=decision,
        decision_reason=decision_reason,
        sanity_passed=sanity_passed,
        sanity_issues_json=sanity_issues_json,
        version=version,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row


class TestPeriodOrdering:
    def test_quarter_chronological_sort(self, db_session):
        result = sort_periods([
            "Q3-2025", "Q1-2024", "Q4-2024", "Q2-2025", "Q1-2025",
        ])
        assert result == [
            "Q1-2024", "Q4-2024", "Q1-2025", "Q2-2025", "Q3-2025",
        ]

    def test_mixed_types_sort(self, db_session):
        result = sort_periods([
            "FY-2024", "Q1-2025", "H1-2025", "Q3-2024",
        ])
        assert result == [
            "Q3-2024", "FY-2024", "Q1-2025", "H1-2025",
        ]

    def test_unknown_sorts_last(self, db_session):
        result = sort_periods(["Q1-2025", "UNKNOWN", "Q4-2024"])
        assert result == ["Q4-2024", "Q1-2025", "UNKNOWN"]

    def test_unknown_excluded_from_latest(self, db_session):
        _make_record(db_session, metric="Revenue", value=100, period="Q1-2025")
        _make_record(
            db_session, metric="Revenue", value=200, period="UNKNOWN"
        )
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        assert result.latest_period == "Q1-2025"
        assert result.previous_period is None
        assert "UNKNOWN" in result.periods_available


class TestAnalysisEmpty:
    def test_no_data_returns_none(self, db_session):
        svc = CompanyAnalysisService(db_session)
        result = svc.analyze("nonexistent-company")
        assert result is None


class TestAnalysisSinglePeriod:
    def test_single_period_no_comparison(self, db_session):
        _make_record(db_session, metric="Revenue", value=1000, period="Q1-2025")
        _make_record(db_session, metric="EBITDA", value=200, period="Q1-2025")
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        assert result is not None
        assert result.latest_period == "Q1-2025"
        assert result.previous_period is None
        assert result.periods_available == ["Q1-2025"]
        for c in result.comparisons:
            assert c.previous_value is None
            assert c.delta is None
            assert c.severity == "normal"

    def test_single_period_missing_metrics(self, db_session):
        _make_record(db_session, metric="Revenue", value=1000, period="Q1-2025")
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        missing_metrics = {m.metric for m in result.missing}
        assert "EBITDA" in missing_metrics
        assert "Gross Profit" in missing_metrics
        assert "Net Income" in missing_metrics
        assert "Cash" in missing_metrics
        assert "Assets" not in missing_metrics

        for m in result.missing:
            assert m.type == "absent_in_latest"


class TestAnalysisTwoPeriods:
    def test_period_comparison(self, db_session):
        _make_record(db_session, metric="Revenue", value=1000, period="Q1-2025")
        _make_record(db_session, metric="Revenue", value=750, period="Q2-2025")
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        assert result.latest_period == "Q2-2025"
        assert result.previous_period == "Q1-2025"
        rev_comp = next(c for c in result.comparisons if c.metric == "Revenue")
        assert rev_comp.current_value == 750
        assert rev_comp.previous_value == 1000
        assert rev_comp.delta == -250
        assert rev_comp.delta_percent == -25.0
        assert rev_comp.severity == "warning"

    def test_critical_revenue_drop(self, db_session):
        _make_record(db_session, metric="Revenue", value=1000, period="Q1-2025")
        _make_record(db_session, metric="Revenue", value=400, period="Q2-2025")
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        rev = next(c for c in result.comparisons if c.metric == "Revenue")
        assert rev.severity == "critical"
        assert rev.delta_percent == -60.0

    def test_ebitda_sign_flip(self, db_session):
        _make_record(db_session, metric="EBITDA", value=500, period="Q1-2025")
        _make_record(db_session, metric="EBITDA", value=-100, period="Q2-2025")
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        eb = next(c for c in result.comparisons if c.metric == "EBITDA")
        assert eb.severity == "critical"
        assert "negative" in eb.explanation.lower()

    def test_revision_prefers_approved(self, db_session):
        _make_record(
            db_session, metric="Revenue", value=500, period="Q1-2025",
            status="PENDING", version=1,
        )
        _make_record(
            db_session, metric="Revenue", value=600, period="Q1-2025",
            status="APPROVED", version=2,
        )
        _make_record(db_session, metric="Revenue", value=700, period="Q2-2025")
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        rev = next(c for c in result.comparisons if c.metric == "Revenue")
        assert rev.previous_value == 600

    def test_period_regression_detected(self, db_session):
        _make_record(db_session, metric="Revenue", value=1000, period="Q1-2025")
        _make_record(db_session, metric="EBITDA", value=200, period="Q1-2025")
        _make_record(db_session, metric="Revenue", value=1100, period="Q2-2025")
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        regressed = [m for m in result.missing if m.type == "period_regression"]
        assert len(regressed) == 1
        assert regressed[0].metric == "EBITDA"
        assert "was reported" in regressed[0].reason


class TestMissingTypes:
    def test_partial_balance_sheet_type(self, db_session):
        _make_record(db_session, metric="Assets", value=1000, period="Q1-2025")
        _make_record(db_session, metric="Liabilities", value=600, period="Q1-2025")
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        bs_missing = [m for m in result.missing if m.type == "partial_balance_sheet"]
        assert len(bs_missing) == 1
        assert bs_missing[0].metric == "Equity"


class TestAnomalies:
    def test_sanity_failure_surfaced(self, db_session):
        issues = ["EBITDA > Revenue"]
        _make_record(
            db_session, metric="EBITDA", value=2000, period="Q1-2025",
            sanity_passed="false",
            sanity_issues_json=json.dumps(issues),
        )
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        assert len(result.anomalies) >= 1
        a = next(a for a in result.anomalies if a.issue == "EBITDA > Revenue")
        assert a.severity == "critical"
        assert a.kind == "sanity_failure"

    def test_hard_block_surfaced(self, db_session):
        # Hard block WITHOUT sanity failure — should appear
        _make_record(
            db_session, metric="Revenue", value=100, period="Q1-2025",
            decision="FLAG",
            decision_reason="Hard blocked: Missing/unknown period",
        )
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        hard_blocks = [a for a in result.anomalies if a.kind == "hard_block"]
        assert len(hard_blocks) >= 1

    def test_sanity_plus_hard_block_deduplicates(self, db_session):
        """When a record has both sanity failure and hard block,
        only the sanity_failure should surface (not both)."""
        _make_record(
            db_session, metric="EBITDA", value=2000, period="Q1-2025",
            sanity_passed="false",
            sanity_issues_json=json.dumps(["EBITDA > Revenue"]),
            decision="FLAG",
            decision_reason="Hard blocked: Sanity critical: EBITDA > Revenue",
        )
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        # Should have sanity_failure but NOT hard_block for same record
        kinds = [a.kind for a in result.anomalies]
        assert "sanity_failure" in kinds
        assert "hard_block" not in kinds

    def test_weak_mapping_surfaced(self, db_session):
        _make_record(
            db_session, metric="Revenue", value=100, period="Q1-2025",
            mapping_method="rule_based",
            mapping_score=0.6,
            mapping_reason="Partial match: 'Total Sales Revenue' -> Revenue",
        )
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        weak = [a for a in result.anomalies if a.kind == "weak_mapping"]
        assert len(weak) == 1
        assert weak[0].severity == "warning"

    def test_rejected_records_excluded(self, db_session):
        _make_record(
            db_session, metric="EBITDA", value=999, period="Q1-2025",
            status="REJECTED",
            sanity_passed="false",
            sanity_issues_json=json.dumps(["bad data"]),
        )
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        assert len(result.anomalies) == 0


class TestTrustAssessment:
    def test_confidence_summary(self, db_session):
        _make_record(
            db_session, metric="Revenue", value=1000, period="Q1-2025",
            status="APPROVED", confidence_total=0.9,
        )
        _make_record(
            db_session, metric="EBITDA", value=200, period="Q1-2025",
            status="PENDING", confidence_total=0.4,
        )
        _make_record(
            db_session, metric="Cash", value=500, period="Q1-2025",
            status="REJECTED", confidence_total=0.2,
        )
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)
        trust = result.trust

        assert trust.total_records == 3
        assert trust.approved_count == 1
        assert trust.pending_count == 1
        assert trust.rejected_count == 1
        assert trust.low_confidence_count == 2
        # Raw avg of non-rejected = (0.9 + 0.4) / 2 = 0.65
        # No sanity failures or hard blocks -> no penalty
        assert abs(trust.overall_score - 0.65) < 0.01
        assert trust.label == "medium"
        assert trust.weakest_score == 0.4

    def test_trust_penalty_for_failures(self, db_session):
        """Trust score should drop when sanity failures are present."""
        # 2 good records, 1 sanity failure
        _make_record(
            db_session, metric="Revenue", value=1000, period="Q1-2025",
            confidence_total=0.9,
        )
        _make_record(
            db_session, metric="EBITDA", value=200, period="Q1-2025",
            confidence_total=0.9,
        )
        _make_record(
            db_session, metric="Cash", value=500, period="Q1-2025",
            confidence_total=0.7,
            sanity_passed="false",
            sanity_issues_json=json.dumps(["some issue"]),
            decision="FLAG",
            decision_reason="Hard blocked: Sanity critical: some issue",
        )
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)
        trust = result.trust

        # Raw avg = (0.9 + 0.9 + 0.7) / 3 = 0.833
        # Failure rate = 2/3 (sanity_fails=1, hard_blocked=1, but same
        # record counts once for sanity, once for hard_blocked)
        # Actually: sanity_fails=1, hard_blocked=1
        # failure_rate = (1+1)/3 = 0.667, penalty = 0.667 * 0.3 = 0.2
        # overall = 0.833 - 0.2 = 0.633
        assert trust.overall_score < 0.8  # Should NOT be "high"
        assert trust.label in ("medium", "low")

    def test_high_trust_label(self, db_session):
        _make_record(
            db_session, metric="Revenue", value=1000, period="Q1-2025",
            status="APPROVED", confidence_total=0.95,
        )
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)
        assert result.trust.label == "high"

    def test_low_trust_label(self, db_session):
        _make_record(
            db_session, metric="Revenue", value=1000, period="Q1-2025",
            status="PENDING", confidence_total=0.3,
        )
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)
        assert result.trust.label == "low"

    def test_empty_trust(self, db_session):
        svc = CompanyAnalysisService(db_session)
        trust = svc._assess_trust("empty-company")
        assert trust.total_records == 0
        assert trust.overall_score == 0.0
        assert trust.label == "low"

    def test_flagged_counted(self, db_session):
        _make_record(
            db_session, metric="Revenue", value=100, period="Q1-2025",
            decision="FLAG", decision_reason="Hard blocked: sanity failure",
            confidence_total=0.3,
        )
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        assert result.trust.flagged_count == 1
        assert result.trust.hard_blocked_count == 1

    def test_trust_label_boundaries(self, db_session):
        cases = [
            (0.0, "low"), (0.49, "low"), (0.5, "medium"),
            (0.79, "medium"), (0.8, "high"), (1.0, "high"),
        ]
        for score, expected in cases:
            assert _trust_label(score) == expected


class TestAnalysisOutputSchema:
    def test_output_has_all_fields(self, db_session):
        _make_record(db_session, metric="Revenue", value=1000, period="Q1-2025")
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        assert result.company_id == COMPANY
        assert result.latest_period is not None
        assert result.previous_period is None
        assert isinstance(result.periods_available, list)
        assert isinstance(result.comparisons, list)
        assert isinstance(result.anomalies, list)
        assert isinstance(result.missing, list)
        assert result.trust is not None
        assert result.trust.label in ("high", "medium", "low")
        assert isinstance(result.upload_count, int)
        assert isinstance(result.comparison_warnings, int)
        assert isinstance(result.anomaly_count, int)
        assert isinstance(result.missing_count, int)

    def test_two_period_has_previous(self, db_session):
        _make_record(db_session, metric="Revenue", value=1000, period="Q1-2025")
        _make_record(db_session, metric="Revenue", value=1100, period="Q2-2025")
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        assert result.previous_period == "Q1-2025"
        assert result.latest_period == "Q2-2025"
