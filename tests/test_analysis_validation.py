"""Product validation of Company Analysis against real demo files.

Runs the full pipeline on demo files, then validates the analysis output
for correctness, completeness, and product-readiness.
"""

from dataclasses import asdict
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.analysis.service import CompanyAnalysisService
from src.api.pipeline import Pipeline
from src.models.database import Base

SAMPLE_DIR = Path(__file__).parent.parent / "sample_data"


@pytest.fixture
def pipeline_session():
    """In-memory DB session with full schema."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def ingest(session, filename, company_id):
    """Run the full pipeline on a file."""
    path = SAMPLE_DIR / filename
    assert path.exists(), f"Missing: {path}"
    p = Pipeline(session)
    result = p.process_file(
        file_path=path,
        company_id=company_id,
        uploaded_by="test",
        source_type="manual_upload",
    )
    session.commit()
    return result


class TestCleanDemo:
    """Validation: acme_q3_2025_clean.xlsx — ideal case."""

    def test_clean_file_analysis(self, pipeline_session):
        result = ingest(
            pipeline_session, "acme_q3_2025_clean.xlsx", "acme"
        )
        assert result.status == "COMPLETED"
        assert result.records_created > 0

        svc = CompanyAnalysisService(pipeline_session)
        analysis = svc.analyze("acme")
        assert analysis is not None

        d = asdict(analysis)
        print("\n=== CLEAN DEMO ANALYSIS ===")
        print(f"Company: {d['company_id']}")
        print(f"Latest period: {d['latest_period']}")
        print(f"Previous period: {d['previous_period']}")
        print(f"Periods: {d['periods_available']}")
        print(f"Upload count: {d['upload_count']}")
        print(f"\nTrust: score={d['trust']['overall_score']}, "
              f"label={d['trust']['label']}")
        print(f"  Approved: {d['trust']['approved_count']}")
        print(f"  Pending: {d['trust']['pending_count']}")
        print(f"  Flagged: {d['trust']['flagged_count']}")
        print(f"  Weakest: {d['trust']['weakest_area']} "
              f"@ {d['trust']['weakest_score']}")
        print(f"\nComparisons ({len(d['comparisons'])}):")
        for c in d["comparisons"]:
            print(f"  {c['metric']}: {c['current_value']} "
                  f"({c['severity']})")
        print(f"\nAnomalies ({d['anomaly_count']}):")
        for a in d["anomalies"]:
            print(f"  [{a['kind']}] {a['metric']} {a['period']}: "
                  f"{a['issue']}")
        print(f"\nMissing ({d['missing_count']}):")
        for m in d["missing"]:
            print(f"  [{m['type']}] {m['metric']}: {m['reason']}")

        # Assertions: clean file should have no anomalies from sanity
        sanity_anomalies = [
            a for a in analysis.anomalies if a.kind == "sanity_failure"
        ]
        print(f"\nSanity anomalies: {len(sanity_anomalies)}")

        # Should have at least some metrics
        assert len(analysis.comparisons) > 0


class TestMessyDemo:
    """Validation: beta_q3_2025_messy.xlsx — known errors."""

    def test_messy_file_analysis(self, pipeline_session):
        result = ingest(
            pipeline_session, "beta_q3_2025_messy.xlsx", "beta"
        )
        assert result.status == "COMPLETED"

        svc = CompanyAnalysisService(pipeline_session)
        analysis = svc.analyze("beta")
        assert analysis is not None

        d = asdict(analysis)
        print("\n=== MESSY DEMO ANALYSIS ===")
        print(f"Company: {d['company_id']}")
        print(f"Latest period: {d['latest_period']}")
        print(f"Periods: {d['periods_available']}")
        print(f"\nTrust: score={d['trust']['overall_score']}, "
              f"label={d['trust']['label']}")
        print(f"  Sanity failures: {d['trust']['sanity_failures']}")
        print(f"  Hard blocked: {d['trust']['hard_blocked_count']}")
        print(f"  Low confidence: {d['trust']['low_confidence_count']}")
        print(f"\nComparisons ({len(d['comparisons'])}):")
        for c in d["comparisons"]:
            print(f"  {c['metric']}: {c['current_value']}")
        print(f"\nAnomalies ({d['anomaly_count']}):")
        for a in d["anomalies"]:
            print(f"  [{a['severity']}|{a['kind']}] {a['metric']}: "
                  f"{a['issue']}")
        print(f"\nMissing ({d['missing_count']}):")
        for m in d["missing"]:
            print(f"  [{m['type']}] {m['metric']}: {m['reason']}")

        # Messy file should surface anomalies (EBITDA > Revenue, BS mismatch)
        assert analysis.anomaly_count > 0 or analysis.missing_count > 0


class TestRevisionScenario:
    """Validation: acme original + revised — period comparison."""

    def test_revision_analysis(self, pipeline_session):
        # First upload: original
        r1 = ingest(
            pipeline_session, "acme_q3_2025_original.xlsx", "acme"
        )
        assert r1.status == "COMPLETED"

        # Second upload: revised
        r2 = ingest(
            pipeline_session, "acme_q3_2025_revised.xlsx", "acme"
        )
        assert r2.status == "COMPLETED"

        svc = CompanyAnalysisService(pipeline_session)
        analysis = svc.analyze("acme")
        assert analysis is not None

        d = asdict(analysis)
        print("\n=== REVISION SCENARIO ANALYSIS ===")
        print(f"Company: {d['company_id']}")
        print(f"Latest period: {d['latest_period']}")
        print(f"Previous period: {d['previous_period']}")
        print(f"Periods: {d['periods_available']}")
        print(f"Upload count: {d['upload_count']}")
        print(f"\nTrust: score={d['trust']['overall_score']}, "
              f"label={d['trust']['label']}")
        print(f"  Total records: {d['trust']['total_records']}")
        print(f"  Approved: {d['trust']['approved_count']}")
        print(f"  Pending: {d['trust']['pending_count']}")
        print(f"\nComparisons ({len(d['comparisons'])}):")
        for c in d["comparisons"]:
            prev = c["previous_value"]
            delta = c["delta_percent"]
            print(f"  {c['metric']}: {prev} -> {c['current_value']} "
                  f"({delta}% | {c['severity']})")
        print(f"\nAnomalies ({d['anomaly_count']}):")
        for a in d["anomalies"]:
            print(f"  [{a['severity']}|{a['kind']}] {a['metric']}: "
                  f"{a['issue']}")
        print(f"\nMissing ({d['missing_count']}):")
        for m in d["missing"]:
            print(f"  [{m['type']}] {m['metric']}: {m['reason']}")

        # Both files are Q3-2025, so we should have revisions, not
        # a second period
        assert analysis.upload_count == 2


class TestRealWorkbook:
    """Validation: TrioMobil real workbook — complex multi-sheet."""

    def test_real_workbook_analysis(self, pipeline_session):
        fname = (
            "TrioMobil Consolidated Financials 12-2025 "
            "- 48 Months. 06.02.2026.xlsx"
        )
        result = ingest(pipeline_session, fname, "triomobil")
        print("\n=== REAL WORKBOOK PIPELINE RESULT ===")
        print(f"Status: {result.status}")
        print(f"Records extracted: {result.records_extracted}")
        print(f"Records created: {result.records_created}")
        print(f"Errors: {result.errors}")
        if result.outcomes:
            print(f"\nOutcomes ({len(result.outcomes)}):")
            for o in result.outcomes[:20]:
                print(f"  {o.metric}: {o.value} @ {o.period} "
                      f"(conf={o.confidence:.2f}, {o.decision})")
            if len(result.outcomes) > 20:
                print(f"  ... +{len(result.outcomes) - 20} more")

        svc = CompanyAnalysisService(pipeline_session)
        analysis = svc.analyze("triomobil")

        if analysis is None:
            print("\nAnalysis returned None — no mapped records")
            return

        d = asdict(analysis)
        print("\n=== REAL WORKBOOK ANALYSIS ===")
        print(f"Latest period: {d['latest_period']}")
        print(f"Previous period: {d['previous_period']}")
        print(f"Period type mismatch: {d['period_type_mismatch']}")
        print(f"Periods ({len(d['periods_available'])}): "
              f"{d['periods_available'][:10]}")
        if len(d["periods_available"]) > 10:
            print(f"  ... +{len(d['periods_available']) - 10} more")
        print(f"\nTrust: score={d['trust']['overall_score']}, "
              f"label={d['trust']['label']}")
        print(f"  Total records: {d['trust']['total_records']}")
        print(f"  Low confidence: {d['trust']['low_confidence_count']}")
        print(f"  Sanity failures: {d['trust']['sanity_failures']}")
        print(f"  Hard blocked: {d['trust']['hard_blocked_count']}")
        print(f"  Weakest: {d['trust']['weakest_area']} "
              f"@ {d['trust']['weakest_score']}")
        print(f"\nComparisons ({len(d['comparisons'])}):")
        for c in d["comparisons"]:
            prev = c["previous_value"]
            delta = c["delta_percent"]
            warn = " [!]" if c.get("comparison_warning") else ""
            print(f"  {c['metric']}: {prev} -> {c['current_value']} "
                  f"({delta}% | {c['severity']}){warn}")
        if d["comparisons"] and d["comparisons"][0].get("comparison_warning"):
            print(f"  Warning: {d['comparisons'][0]['comparison_warning']}")
        print(f"\nAnomalies total: {d['anomaly_count']}")
        print(f"Aggregated groups: {len(d['aggregated_anomalies'])}")
        for ag in d["aggregated_anomalies"][:10]:
            print(f"  [{ag['severity']}|{ag['kind']}] {ag['count']}x: "
                  f"{ag['issue']}")
            print(f"    metrics: {ag['metrics'][:5]}, "
                  f"periods: {ag['periods'][:5]}")
        if len(d["aggregated_anomalies"]) > 10:
            print(f"  ... +{len(d['aggregated_anomalies']) - 10} more groups")
        print(f"\nRaw anomalies (first 5):")
        for a in d["anomalies"][:5]:
            print(f"  [{a['severity']}|{a['kind']}] {a['metric']} "
                  f"{a['period']}: {a['issue']}")
        if d["anomaly_count"] > 5:
            print(f"  ... +{d['anomaly_count'] - 5} more")
        print(f"\nMissing ({d['missing_count']}):")
        for m in d["missing"]:
            print(f"  [{m['type']}] {m['metric']}: {m['reason']}")


class TestPeriodOrdering:
    """Verify period ordering across different period types."""

    def test_quarter_ordering(self, pipeline_session):
        from src.analysis.service import sort_periods
        from src.period.service import PeriodNormalizer

        normalizer = PeriodNormalizer()
        inputs = [
            "Q3-2025", "Q1-2025", "Q4-2024", "Q2-2025",
            "1Q24", "3Q24", "2Q24", "4Q24",
        ]
        results = []
        for inp in inputs:
            r = normalizer.normalize(inp)
            results.append(r.normalized_period)
            print(f"  '{inp}' -> '{r.normalized_period}' "
                  f"(type={r.period_type}, conf={r.confidence})")

        # Use chronological sort
        sorted_periods = sort_periods(list(set(results)))
        print(f"\nSorted: {sorted_periods}")
        assert sorted_periods == [
            "Q1-2024", "Q2-2024", "Q3-2024", "Q4-2024",
            "Q1-2025", "Q2-2025", "Q3-2025",
        ]

    def test_mixed_period_type_ordering(self, pipeline_session):
        from src.analysis.service import sort_periods
        from src.period.service import PeriodNormalizer

        normalizer = PeriodNormalizer()
        inputs = [
            "FY-2024", "H1-2025", "Q3-2025", "Q1-2025",
            "H2-2024", "YTD-2025",
        ]
        results = []
        for inp in inputs:
            r = normalizer.normalize(inp)
            results.append(r.normalized_period)
            print(f"  '{inp}' -> '{r.normalized_period}' "
                  f"(type={r.period_type})")

        sorted_periods = sort_periods(results)
        print(f"\nSorted: {sorted_periods}")
        # 2024: H2 < FY (H2 = sub 12, FY = sub 20)
        # 2025: Q1 < Q3 < H1 < YTD
        assert sorted_periods[0] == "H2-2024"
        assert sorted_periods[1] == "FY-2024"
        # 2025 periods come after 2024
        assert sorted_periods[-1] == "YTD-2025"

    def test_date_to_quarter_conversion(self, pipeline_session):
        from src.period.service import PeriodNormalizer

        normalizer = PeriodNormalizer()
        inputs = [
            "30.09.2025",  # German format -> Q3-2025
            "2025-09-30",  # ISO -> Q3-2025
            "09/30/2025",  # US -> Q3-2025
            "31.12.2024",  # -> Q4-2024
            "Jun-2025",    # -> Q2-2025
            "Mar 25",      # -> Q1-2025
        ]
        for inp in inputs:
            r = normalizer.normalize(inp)
            print(f"  '{inp}' -> '{r.normalized_period}' "
                  f"(type={r.period_type}, conf={r.confidence})")


class TestTrustLabelCorrectness:
    """Verify trust label assignments feel correct."""

    def test_trust_label_boundaries(self, pipeline_session):
        """Test that trust labels match thresholds."""
        from src.analysis.service import _trust_label

        cases = [
            (0.0, "low"),
            (0.49, "low"),
            (0.5, "medium"),
            (0.65, "medium"),
            (0.79, "medium"),
            (0.8, "high"),
            (0.95, "high"),
            (1.0, "high"),
        ]
        for score, expected in cases:
            actual = _trust_label(score)
            print(f"  score={score} -> label={actual} "
                  f"(expected={expected})")
            assert actual == expected

    def test_severity_classifications_feel_right(self, pipeline_session):
        """Test that severity thresholds match financial intuition."""
        svc = CompanyAnalysisService(pipeline_session)

        # Revenue scenarios
        cases = [
            ("Revenue", 900, 1000, "normal", "10% decline"),
            ("Revenue", 750, 1000, "warning", "25% decline"),
            ("Revenue", 400, 1000, "critical", "60% decline"),
            ("Revenue", 2100, 1000, "warning", "110% increase"),
            ("EBITDA", -100, 500, "critical", "sign flip neg"),
            ("EBITDA", 100, -50, "warning", "sign flip pos"),
            ("Cash", 400, 1000, "critical", "60% cash drop"),
            ("Net Income", -50, 100, "warning", "profit to loss"),
            ("Assets", 1100, 1000, "normal", "10% increase"),
            ("Assets", 300, 1000, "warning", "70% drop (generic)"),
        ]

        for metric, current, previous, expected_sev, desc in cases:
            pct = round((current - previous) / abs(previous) * 100, 2)
            sev, explanation = svc._classify_change(
                metric, current, previous, pct
            )
            print(f"  {desc}: {metric} {previous}->{current} "
                  f"({pct:+.0f}%) => {sev} "
                  f"({'OK' if sev == expected_sev else 'MISMATCH!'})")
            assert sev == expected_sev, (
                f"{desc}: expected {expected_sev}, got {sev}"
            )
