"""Company Analysis Service.

Answers 4 questions about a company's financial data:
1. What changed vs the previous period?
2. What is wrong or suspicious?
3. What is missing?
4. How much can we trust this data?

Uses ONLY existing modules: storage, change_detection logic, sanity rules,
confidence scores. No LLM. No new extraction.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.core.enums import StandardMetric
from src.models.database import FinancialRecord
from src.storage.service import StorageService

# The metrics we expect in a complete financial picture.
# Income statement metrics
INCOME_METRICS = {
    StandardMetric.REVENUE.value,
    StandardMetric.GROSS_PROFIT.value,
    StandardMetric.EBITDA.value,
    StandardMetric.NET_INCOME.value,
}

# Balance sheet metrics
BALANCE_METRICS = {
    StandardMetric.ASSETS.value,
    StandardMetric.LIABILITIES.value,
    StandardMetric.EQUITY.value,
}

# Liquidity
LIQUIDITY_METRICS = {
    StandardMetric.CASH.value,
}

ALL_EXPECTED_METRICS = INCOME_METRICS | BALANCE_METRICS | LIQUIDITY_METRICS

# Period type ordering for chronological sort.
# Lower number = earlier in the year for same-year periods.
_PERIOD_TYPE_ORDER = {"Q": 0, "H": 1, "FY": 2, "YTD": 3, "UNKNOWN": 9}


def _period_sort_key(period: str) -> tuple[int, int, str]:
    """Sort key that orders periods chronologically.

    Returns (year, sub_order, original) so that:
    - Q1-2024 < Q2-2024 < ... < Q4-2024 < Q1-2025
    - FY-2024 sorts after all quarters of 2024
    - UNKNOWN sorts last
    """
    if period == "UNKNOWN":
        return (9999, 0, period)

    # Extract year (last 4 digits)
    year_match = re.search(r"(\d{4})$", period)
    year = int(year_match.group(1)) if year_match else 9998

    # Extract type prefix and number
    # Q1-2025 -> type=Q, num=1
    # H2-2024 -> type=H, num=2
    # FY-2024 -> type=FY, num=0
    # YTD-2025 -> type=YTD, num=0
    prefix_match = re.match(r"([A-Za-z]+)(\d?)-", period)
    if prefix_match:
        ptype = prefix_match.group(1).upper()
        pnum = int(prefix_match.group(2)) if prefix_match.group(2) else 0
    else:
        ptype = "UNKNOWN"
        pnum = 0

    # Build sub-order: type_order * 10 + number
    type_order = _PERIOD_TYPE_ORDER.get(ptype, 8)
    sub_order = type_order * 10 + pnum

    return (year, sub_order, period)


def sort_periods(periods: list[str]) -> list[str]:
    """Sort periods chronologically."""
    return sorted(periods, key=_period_sort_key)


@dataclass
class MetricComparison:
    """One metric compared across two periods."""

    metric: str
    current_value: float
    current_period: str
    previous_value: float | None
    previous_period: str | None
    delta: float | None = None
    delta_percent: float | None = None
    severity: str = "normal"  # normal | warning | critical
    explanation: str = ""


@dataclass
class Anomaly:
    """A suspicious data point with explanation."""

    metric: str
    period: str
    value: float
    issue: str
    kind: str  # sanity_failure | hard_block | weak_mapping
    severity: str  # warning | critical
    record_id: str


@dataclass
class MissingItem:
    """A metric/period gap that should probably exist."""

    metric: str
    period: str
    reason: str
    type: str  # absent_in_latest | partial_balance_sheet | period_regression


@dataclass
class TrustAssessment:
    """Confidence summary for a company's data."""

    overall_score: float  # 0-1
    label: str  # high | medium | low
    total_records: int
    approved_count: int
    pending_count: int
    rejected_count: int
    flagged_count: int
    low_confidence_count: int  # records with confidence < 0.5
    sanity_failures: int
    hard_blocked_count: int
    weakest_area: str  # which metric/period has the lowest confidence
    weakest_score: float


@dataclass
class CompanyAnalysis:
    """Complete analysis result for one company."""

    company_id: str
    periods_available: list[str]
    latest_period: str | None
    previous_period: str | None
    upload_count: int

    # Q1: What changed?
    comparisons: list[MetricComparison]

    # Q2: What is wrong?
    anomalies: list[Anomaly]

    # Q3: What is missing?
    missing: list[MissingItem]

    # Q4: Trust level
    trust: TrustAssessment

    # Summary counts for quick consumption
    comparison_warnings: int = 0
    anomaly_count: int = 0
    missing_count: int = 0


def _trust_label(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


class CompanyAnalysisService:
    """Produces structured analysis for a company using existing modules only."""

    def __init__(self, session: Session):
        self.session = session
        self.storage = StorageService(session)

    def analyze(self, company_id: str) -> CompanyAnalysis | None:
        """Run full analysis for a company. Returns None if no data exists."""
        raw_periods = self.storage.get_distinct_periods(company_id)
        if not raw_periods:
            return None

        # Sort chronologically and exclude UNKNOWN from latest/previous
        periods = sort_periods(raw_periods)
        known_periods = [p for p in periods if p != "UNKNOWN"]

        best = self.storage.get_latest_per_metric_period(company_id)
        uploads = self.storage.get_upload_history(company_id)

        latest_period = known_periods[-1] if known_periods else None
        previous_period = (
            known_periods[-2] if len(known_periods) >= 2 else None
        )

        comparisons = self._build_comparisons(
            best, latest_period, previous_period
        )
        anomalies = self._find_anomalies(company_id)
        missing = self._find_missing(best, latest_period, known_periods)
        trust = self._assess_trust(company_id)

        comparison_warnings = sum(
            1 for c in comparisons if c.severity in ("warning", "critical")
        )

        return CompanyAnalysis(
            company_id=company_id,
            periods_available=periods,
            latest_period=latest_period,
            previous_period=previous_period,
            upload_count=len(uploads),
            comparisons=comparisons,
            anomalies=anomalies,
            missing=missing,
            trust=trust,
            comparison_warnings=comparison_warnings,
            anomaly_count=len(anomalies),
            missing_count=len(missing),
        )

    # ──────────────────────────────────────────────
    # Q1: What changed vs previous period?
    # ──────────────────────────────────────────────

    def _build_comparisons(
        self,
        best: dict[tuple[str, str], object],
        latest_period: str | None,
        previous_period: str | None,
    ) -> list[MetricComparison]:
        if not latest_period:
            return []

        comparisons = []
        for metric_name in sorted(ALL_EXPECTED_METRICS):
            current_key = (metric_name, latest_period)
            current_sr = best.get(current_key)
            if current_sr is None:
                continue

            current_value = current_sr.record.value

            previous_value = None
            if previous_period:
                prev_key = (metric_name, previous_period)
                prev_sr = best.get(prev_key)
                if prev_sr is not None:
                    previous_value = prev_sr.record.value

            delta = None
            delta_pct = None
            severity = "normal"
            explanation = ""

            if previous_value is not None:
                delta = current_value - previous_value
                if previous_value != 0:
                    delta_pct = round(
                        (delta / abs(previous_value)) * 100, 2
                    )

                # Classify severity
                severity, explanation = self._classify_change(
                    metric_name, current_value, previous_value, delta_pct
                )

            comparisons.append(
                MetricComparison(
                    metric=metric_name,
                    current_value=current_value,
                    current_period=latest_period,
                    previous_value=previous_value,
                    previous_period=previous_period,
                    delta=delta,
                    delta_percent=delta_pct,
                    severity=severity,
                    explanation=explanation,
                )
            )

        return comparisons

    def _classify_change(
        self,
        metric: str,
        current: float,
        previous: float,
        pct: float | None,
    ) -> tuple[str, str]:
        """Return (severity, explanation) for a period-over-period change."""
        if pct is None:
            return "normal", ""

        abs_pct = abs(pct)

        # Revenue decline > 20% is a warning, > 50% is critical
        if metric == StandardMetric.REVENUE.value:
            if pct < -50:
                return (
                    "critical",
                    f"Revenue dropped {abs_pct:.0f}% — verify",
                )
            if pct < -20:
                return "warning", f"Revenue declined {abs_pct:.0f}%"
            if pct > 100:
                return (
                    "warning",
                    f"Revenue more than doubled (+{pct:.0f}%) — verify",
                )

        # EBITDA sign flip is always suspicious
        if metric == StandardMetric.EBITDA.value:
            if previous > 0 and current < 0:
                return (
                    "critical",
                    "EBITDA flipped from positive to negative",
                )
            if previous < 0 and current > 0:
                return "warning", "EBITDA turned positive — verify"

        # Cash > 50% drop
        if metric == StandardMetric.CASH.value and pct < -50:
            return (
                "critical",
                f"Cash dropped {abs_pct:.0f}% — liquidity concern",
            )

        # Net income sign flip
        if metric == StandardMetric.NET_INCOME.value:
            if previous > 0 and current < 0:
                return "warning", "Company moved from profit to loss"

        # Generic large swing
        if abs_pct > 100:
            return "warning", f"Large change ({pct:+.0f}%) — verify"
        if abs_pct > 50:
            return "warning", f"Significant change ({pct:+.0f}%)"

        return "normal", ""

    # ──────────────────────────────────────────────
    # Q2: What is wrong or suspicious?
    # ──────────────────────────────────────────────

    def _find_anomalies(self, company_id: str) -> list[Anomaly]:
        """Surface records with sanity failures, hard blocks, or weak mappings.

        Deduplicates: if a record has a sanity_failure, its corresponding
        hard_block (which just echoes the same issue) is suppressed.
        """
        rows = (
            self.session.query(FinancialRecord)
            .filter(
                FinancialRecord.company_id == company_id,
                FinancialRecord.status != "REJECTED",
            )
            .all()
        )

        anomalies = []
        # Track record IDs that have sanity failures so we skip
        # redundant hard_block entries for the same record.
        sanity_record_ids: set[str] = set()

        for row in rows:
            # Sanity failures (highest priority)
            if row.sanity_passed == "false":
                sanity_record_ids.add(row.id)
                issues = []
                try:
                    issues = json.loads(row.sanity_issues_json or "[]")
                except (json.JSONDecodeError, TypeError):
                    pass
                for issue in issues:
                    anomalies.append(
                        Anomaly(
                            metric=row.metric,
                            period=row.period,
                            value=row.value,
                            issue=issue,
                            kind="sanity_failure",
                            severity="critical",
                            record_id=row.id,
                        )
                    )

        # Second pass: hard blocks and weak mappings (skip duplicates)
        for row in rows:
            # Hard-blocked by confidence engine — skip if already
            # surfaced as sanity_failure for the same record
            if (
                row.decision == "FLAG"
                and row.decision_reason
                and "Hard blocked" in row.decision_reason
                and row.id not in sanity_record_ids
            ):
                block_text = row.decision_reason.replace(
                    "Hard blocked: ", ""
                )
                anomalies.append(
                    Anomaly(
                        metric=row.metric,
                        period=row.period,
                        value=row.value,
                        issue=block_text,
                        kind="hard_block",
                        severity="warning",
                        record_id=row.id,
                    )
                )

            # Low-confidence mapping (partial match with score < 0.8)
            if (
                row.mapping_method == "rule_based"
                and row.mapping_score is not None
                and row.mapping_score < 0.8
                and row.mapping_reason
                and "Partial match" in row.mapping_reason
            ):
                anomalies.append(
                    Anomaly(
                        metric=row.metric,
                        period=row.period,
                        value=row.value,
                        issue=f"Weak mapping: {row.mapping_reason}",
                        kind="weak_mapping",
                        severity="warning",
                        record_id=row.id,
                    )
                )

        return anomalies

    # ──────────────────────────────────────────────
    # Q3: What is missing?
    # ──────────────────────────────────────────────

    def _find_missing(
        self,
        best: dict[tuple[str, str], object],
        latest_period: str | None,
        periods: list[str],
    ) -> list[MissingItem]:
        if not latest_period:
            return []

        missing = []

        # Check which metrics are missing from the latest period
        present_metrics = {
            metric for (metric, period) in best if period == latest_period
        }

        # Income statement completeness
        for m in sorted(INCOME_METRICS):
            if m not in present_metrics:
                missing.append(
                    MissingItem(
                        metric=m,
                        period=latest_period,
                        reason=f"No {m} found for {latest_period}",
                        type="absent_in_latest",
                    )
                )

        # Balance sheet completeness — all 3 must be present together
        bs_present = BALANCE_METRICS & present_metrics
        if 0 < len(bs_present) < 3:
            for m in sorted(BALANCE_METRICS - bs_present):
                missing.append(
                    MissingItem(
                        metric=m,
                        period=latest_period,
                        reason=(
                            f"Partial balance sheet: have "
                            f"{', '.join(sorted(bs_present))} "
                            f"but missing {m}"
                        ),
                        type="partial_balance_sheet",
                    )
                )

        # Cash
        if StandardMetric.CASH.value not in present_metrics:
            missing.append(
                MissingItem(
                    metric=StandardMetric.CASH.value,
                    period=latest_period,
                    reason=(
                        f"No Cash position found for {latest_period}"
                    ),
                    type="absent_in_latest",
                )
            )

        # Period regression: metric present in previous but absent in latest
        if len(periods) >= 2:
            previous_period = periods[-2]
            prev_metrics = {
                metric
                for (metric, period) in best
                if period == previous_period
            }
            regressed = prev_metrics - present_metrics
            for m in sorted(regressed):
                missing.append(
                    MissingItem(
                        metric=m,
                        period=latest_period,
                        reason=(
                            f"{m} was reported in {previous_period} "
                            f"but is missing from {latest_period}"
                        ),
                        type="period_regression",
                    )
                )

        return missing

    # ──────────────────────────────────────────────
    # Q4: How much can we trust this data?
    # ──────────────────────────────────────────────

    def _assess_trust(self, company_id: str) -> TrustAssessment:
        rows = (
            self.session.query(FinancialRecord)
            .filter(FinancialRecord.company_id == company_id)
            .all()
        )

        if not rows:
            return TrustAssessment(
                overall_score=0.0,
                label="low",
                total_records=0,
                approved_count=0,
                pending_count=0,
                rejected_count=0,
                flagged_count=0,
                low_confidence_count=0,
                sanity_failures=0,
                hard_blocked_count=0,
                weakest_area="No data",
                weakest_score=0.0,
            )

        approved = sum(1 for r in rows if r.status == "APPROVED")
        pending = sum(1 for r in rows if r.status == "PENDING")
        rejected = sum(1 for r in rows if r.status == "REJECTED")
        flagged = sum(1 for r in rows if r.decision == "FLAG")
        low_conf = sum(
            1
            for r in rows
            if r.confidence_total is not None and r.confidence_total < 0.5
        )
        sanity_fails = sum(
            1 for r in rows if r.sanity_passed == "false"
        )
        hard_blocked = sum(
            1
            for r in rows
            if r.decision_reason
            and "Hard blocked" in (r.decision_reason or "")
        )

        # Overall score: mean confidence of non-rejected records
        scores = [
            r.confidence_total
            for r in rows
            if r.confidence_total is not None and r.status != "REJECTED"
        ]
        raw_avg = sum(scores) / len(scores) if scores else 0.0

        # Apply penalty for sanity failures and hard blocks.
        # Each failure reduces trust — a dataset with 30% failures
        # should not show "high" trust even if avg confidence is 0.85.
        active_count = len(scores)
        if active_count > 0:
            failure_rate = (sanity_fails + hard_blocked) / active_count
            # Penalty: up to 0.3 reduction at 100% failure rate
            penalty = min(failure_rate * 0.3, 0.3)
            overall = max(raw_avg - penalty, 0.0)
        else:
            overall = 0.0

        # Find weakest area
        weakest_metric = "N/A"
        weakest_score = 1.0
        for r in rows:
            if r.status == "REJECTED":
                continue
            conf = r.confidence_total or 0.0
            if conf < weakest_score:
                weakest_score = conf
                weakest_metric = f"{r.metric} ({r.period})"

        overall_rounded = round(overall, 3)
        return TrustAssessment(
            overall_score=overall_rounded,
            label=_trust_label(overall_rounded),
            total_records=len(rows),
            approved_count=approved,
            pending_count=pending,
            rejected_count=rejected,
            flagged_count=flagged,
            low_confidence_count=low_conf,
            sanity_failures=sanity_fails,
            hard_blocked_count=hard_blocked,
            weakest_area=weakest_metric,
            weakest_score=round(weakest_score, 3),
        )
