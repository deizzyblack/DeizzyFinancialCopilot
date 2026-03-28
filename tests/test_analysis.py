"""Tests for the Company Analysis Service.

Covers:
- Company with single period (no comparison possible)
- Company with two periods + revision
- Missing core metrics detection
- Anomaly surfacing (sanity failures, hard blocks, weak mappings)
- Trust/confidence summary
- Empty company returns None
"""

import json
import uuid
from datetime import UTC, datetime

from src.analysis.service import CompanyAnalysisService
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
        assert result.periods_available == ["Q1-2025"]
        # Comparisons exist but have no previous values
        for c in result.comparisons:
            assert c.previous_value is None
            assert c.delta is None
            assert c.severity == "normal"

    def test_single_period_missing_metrics(self, db_session):
        # Only Revenue — everything else missing
        _make_record(db_session, metric="Revenue", value=1000, period="Q1-2025")
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        missing_metrics = {m.metric for m in result.missing}
        # Should flag EBITDA, Gross Profit, Net Income, Cash
        assert "EBITDA" in missing_metrics
        assert "Gross Profit" in missing_metrics
        assert "Net Income" in missing_metrics
        assert "Cash" in missing_metrics
        # Balance sheet metrics should NOT be flagged (partial rule only applies
        # when at least one BS metric is present)
        assert "Assets" not in missing_metrics


class TestAnalysisTwoPeriods:
    def test_period_comparison(self, db_session):
        # Q1: Revenue 1000
        _make_record(db_session, metric="Revenue", value=1000, period="Q1-2025")
        # Q2: Revenue 750 (25% decline — past the -20% warning threshold)
        _make_record(db_session, metric="Revenue", value=750, period="Q2-2025")
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        assert result.latest_period == "Q2-2025"
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
        # Two records for same metric/period: PENDING v1=500, APPROVED v2=600
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
        # Should use APPROVED value (600), not PENDING (500)
        assert rev.previous_value == 600

    def test_period_regression_detected(self, db_session):
        # Q1 has Revenue + EBITDA, Q2 has only Revenue
        _make_record(db_session, metric="Revenue", value=1000, period="Q1-2025")
        _make_record(db_session, metric="EBITDA", value=200, period="Q1-2025")
        _make_record(db_session, metric="Revenue", value=1100, period="Q2-2025")
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        regressed = [m for m in result.missing if "was reported" in m.reason]
        assert len(regressed) == 1
        assert regressed[0].metric == "EBITDA"


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
        sanity_anomaly = next(a for a in result.anomalies if a.issue == "EBITDA > Revenue")
        assert sanity_anomaly.severity == "critical"

    def test_hard_block_surfaced(self, db_session):
        _make_record(
            db_session, metric="Revenue", value=100, period="Q1-2025",
            decision="FLAG",
            decision_reason="Hard blocked: sanity failure",
        )
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        hard_blocks = [a for a in result.anomalies if "sanity failure" in a.issue]
        assert len(hard_blocks) >= 1

    def test_weak_mapping_surfaced(self, db_session):
        _make_record(
            db_session, metric="Revenue", value=100, period="Q1-2025",
            mapping_method="rule_based",
            mapping_score=0.6,
            mapping_reason="Partial match: 'Total Sales Revenue' → Revenue",
        )
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        weak = [a for a in result.anomalies if "Weak mapping" in a.issue]
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
        assert trust.low_confidence_count == 2  # 0.4 and 0.2
        # Overall only from non-rejected: (0.9 + 0.4) / 2 = 0.65
        assert abs(trust.overall_score - 0.65) < 0.01
        # Weakest should be EBITDA at 0.4 (rejected excluded from weakest)
        assert trust.weakest_score == 0.4

    def test_empty_trust(self, db_session):
        svc = CompanyAnalysisService(db_session)
        trust = svc._assess_trust("empty-company")
        assert trust.total_records == 0
        assert trust.overall_score == 0.0

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


class TestAnalysisOutputSchema:
    def test_output_has_all_fields(self, db_session):
        _make_record(db_session, metric="Revenue", value=1000, period="Q1-2025")
        db_session.commit()

        svc = CompanyAnalysisService(db_session)
        result = svc.analyze(COMPANY)

        assert result.company_id == COMPANY
        assert isinstance(result.periods_available, list)
        assert isinstance(result.comparisons, list)
        assert isinstance(result.anomalies, list)
        assert isinstance(result.missing, list)
        assert result.trust is not None
        assert isinstance(result.upload_count, int)
        assert isinstance(result.comparison_warnings, int)
        assert isinstance(result.anomaly_count, int)
        assert isinstance(result.missing_count, int)
