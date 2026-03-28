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
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.core.enums import StandardMetric
from src.models.database import AuditLog, FinancialRecord
from src.storage.service import StorageService

# The metrics we expect in a complete financial picture.
INCOME_METRICS = {
    StandardMetric.REVENUE.value,
    StandardMetric.GROSS_PROFIT.value,
    StandardMetric.EBITDA.value,
    StandardMetric.NET_INCOME.value,
}

BALANCE_METRICS = {
    StandardMetric.ASSETS.value,
    StandardMetric.LIABILITIES.value,
    StandardMetric.EQUITY.value,
}

LIQUIDITY_METRICS = {
    StandardMetric.CASH.value,
}

ALL_EXPECTED_METRICS = INCOME_METRICS | BALANCE_METRICS | LIQUIDITY_METRICS

_PERIOD_TYPE_ORDER = {"Q": 0, "H": 1, "FY": 2, "YTD": 3, "UNKNOWN": 9}


def _period_sort_key(period: str) -> tuple[int, int, str]:
    """Sort key that orders periods chronologically."""
    if period == "UNKNOWN":
        return (9999, 0, period)

    year_match = re.search(r"(\d{4})$", period)
    year = int(year_match.group(1)) if year_match else 9998

    prefix_match = re.match(r"([A-Za-z]+)(\d?)-", period)
    if prefix_match:
        ptype = prefix_match.group(1).upper()
        pnum = int(prefix_match.group(2)) if prefix_match.group(2) else 0
    else:
        ptype = "UNKNOWN"
        pnum = 0

    type_order = _PERIOD_TYPE_ORDER.get(ptype, 8)
    sub_order = type_order * 10 + pnum

    return (year, sub_order, period)


def sort_periods(periods: list[str]) -> list[str]:
    """Sort periods chronologically."""
    return sorted(periods, key=_period_sort_key)


def _period_type_prefix(period: str) -> str:
    """Extract the period type prefix: Q, H, FY, YTD, or UNKNOWN."""
    if period == "UNKNOWN":
        return "UNKNOWN"
    m = re.match(r"([A-Za-z]+)\d?-", period)
    return m.group(1).upper() if m else "UNKNOWN"


# ──────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────


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
    comparison_warning: str | None = None  # set if period types mismatch


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
class AggregatedAnomaly:
    """Anomalies grouped by issue pattern."""

    kind: str
    issue: str
    severity: str
    count: int
    metrics: list[str]
    periods: list[str]
    sample_record_ids: list[str]


@dataclass
class MissingItem:
    """A metric/period gap that should probably exist."""

    metric: str
    period: str
    reason: str
    type: str  # absent_in_latest | failed_mapping | filtered_noise
    #           | partial_balance_sheet | period_regression


@dataclass
class TrustAssessment:
    """Confidence summary for a company's data."""

    overall_score: float
    label: str  # high | medium | low
    total_records: int
    approved_count: int
    pending_count: int
    rejected_count: int
    flagged_count: int
    low_confidence_count: int
    sanity_failures: int
    hard_blocked_count: int
    weakest_area: str
    weakest_score: float


@dataclass
class CompanyAnalysis:
    """Complete analysis result for one company."""

    company_id: str
    periods_available: list[str]
    latest_period: str | None
    previous_period: str | None
    upload_count: int

    comparisons: list[MetricComparison]
    anomalies: list[Anomaly]
    aggregated_anomalies: list[AggregatedAnomaly]
    missing: list[MissingItem]
    trust: TrustAssessment

    comparison_warnings: int = 0
    anomaly_count: int = 0
    missing_count: int = 0
    period_type_mismatch: bool = False


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

        periods = sort_periods(raw_periods)
        known_periods = [p for p in periods if p != "UNKNOWN"]

        best = self.storage.get_latest_per_metric_period(company_id)
        uploads = self.storage.get_upload_history(company_id)

        latest_period = known_periods[-1] if known_periods else None
        previous_period = (
            known_periods[-2] if len(known_periods) >= 2 else None
        )

        # Detect period type mismatch
        ptm = False
        if latest_period and previous_period:
            lt = _period_type_prefix(latest_period)
            pt = _period_type_prefix(previous_period)
            ptm = lt != pt

        comparisons = self._build_comparisons(
            best, latest_period, previous_period
        )

        # If single period, try revision-aware comparison
        if previous_period is None and latest_period:
            rev_comparisons = self._build_revision_comparisons(
                company_id, latest_period
            )
            if rev_comparisons:
                comparisons = rev_comparisons

        anomalies = self._find_anomalies(company_id)
        aggregated = self._aggregate_anomalies(anomalies)

        # Get pipeline context for missing classification
        pipeline_ctx = self._get_pipeline_context(company_id)
        missing = self._find_missing(
            best, latest_period, known_periods, pipeline_ctx
        )
        trust = self._assess_trust(company_id)

        comparison_warnings = sum(
            1
            for c in comparisons
            if c.severity in ("warning", "critical")
        )

        return CompanyAnalysis(
            company_id=company_id,
            periods_available=periods,
            latest_period=latest_period,
            previous_period=previous_period,
            upload_count=len(uploads),
            comparisons=comparisons,
            anomalies=anomalies,
            aggregated_anomalies=aggregated,
            missing=missing,
            trust=trust,
            comparison_warnings=comparison_warnings,
            anomaly_count=len(anomalies),
            missing_count=len(missing),
            period_type_mismatch=ptm,
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

        # Detect period type mismatch for warning
        comp_warning = None
        if previous_period:
            lt = _period_type_prefix(latest_period)
            pt = _period_type_prefix(previous_period)
            if lt != pt:
                comp_warning = (
                    f"Comparing {lt} ({latest_period}) vs "
                    f"{pt} ({previous_period}) — "
                    f"different period types may be misleading"
                )

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
                    comparison_warning=comp_warning,
                )
            )

        return comparisons

    def _build_revision_comparisons(
        self,
        company_id: str,
        period: str,
    ) -> list[MetricComparison]:
        """For single-period data with revisions, compare old vs new version."""
        all_records = self.storage.get_all_for_company(company_id)

        # Group by metric for this period — find metrics with multiple versions
        by_metric: dict[str, list] = defaultdict(list)
        for sr in all_records:
            if sr.record.period == period:
                by_metric[sr.record.metric.value].append(sr)

        comparisons = []
        has_any_revision = False

        for metric_name in sorted(ALL_EXPECTED_METRICS):
            records = by_metric.get(metric_name, [])
            if not records:
                continue

            # Sort by version desc — first is latest
            records.sort(key=lambda r: r.version, reverse=True)
            current = records[0]
            current_value = current.record.value

            previous_value = None
            if len(records) >= 2:
                # Find the previous version (prefer APPROVED old version)
                for old in records[1:]:
                    previous_value = old.record.value
                    break
                has_any_revision = True

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
                severity, explanation = self._classify_change(
                    metric_name, current_value, previous_value, delta_pct
                )

            comparisons.append(
                MetricComparison(
                    metric=metric_name,
                    current_value=current_value,
                    current_period=period,
                    previous_value=previous_value,
                    previous_period=period if previous_value else None,
                    delta=delta,
                    delta_percent=delta_pct,
                    severity=severity,
                    explanation=explanation,
                    comparison_warning=(
                        "Comparing revisions within the same period"
                        if previous_value is not None
                        else None
                    ),
                )
            )

        return comparisons if has_any_revision else []

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
                    f"Revenue more than doubled "
                    f"(+{pct:.0f}%) — verify",
                )

        if metric == StandardMetric.EBITDA.value:
            if previous > 0 and current < 0:
                return (
                    "critical",
                    "EBITDA flipped from positive to negative",
                )
            if previous < 0 and current > 0:
                return "warning", "EBITDA turned positive — verify"

        if metric == StandardMetric.CASH.value and pct < -50:
            return (
                "critical",
                f"Cash dropped {abs_pct:.0f}% — liquidity concern",
            )

        if metric == StandardMetric.NET_INCOME.value:
            if previous > 0 and current < 0:
                return "warning", "Company moved from profit to loss"

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
        hard_block is suppressed.
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
        sanity_record_ids: set[str] = set()

        for row in rows:
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

        for row in rows:
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

    def _aggregate_anomalies(
        self, anomalies: list[Anomaly]
    ) -> list[AggregatedAnomaly]:
        """Group anomalies by (kind, issue, severity)."""
        groups: dict[
            tuple[str, str, str], list[Anomaly]
        ] = defaultdict(list)

        for a in anomalies:
            # Normalize issue text for grouping — strip specific values
            issue_key = re.sub(
                r"\d+\.?\d*", "N", a.issue
            )
            groups[(a.kind, issue_key, a.severity)].append(a)

        result = []
        for (kind, _, severity), items in sorted(
            groups.items(),
            key=lambda kv: (-len(kv[1]), kv[0]),
        ):
            metrics = sorted({a.metric for a in items})
            periods = sorted(
                {a.period for a in items}, key=_period_sort_key
            )
            sample_ids = [a.record_id for a in items[:5]]
            result.append(
                AggregatedAnomaly(
                    kind=kind,
                    issue=items[0].issue,
                    severity=severity,
                    count=len(items),
                    metrics=metrics,
                    periods=periods,
                    sample_record_ids=sample_ids,
                )
            )

        return result

    # ──────────────────────────────────────────────
    # Q3: What is missing?
    # ──────────────────────────────────────────────

    def _get_pipeline_context(
        self, company_id: str
    ) -> dict[str, int]:
        """Get pipeline processing stats from audit trail."""
        rows = (
            self.session.query(AuditLog)
            .filter(AuditLog.event_type == "PIPELINE_COMPLETE")
            .all()
        )

        total_unmapped = 0
        total_noise = 0
        for row in rows:
            details = row.details
            if details.get("company_id") == company_id:
                total_unmapped += details.get("unmapped_count", 0)
                total_noise += details.get(
                    "noise_filtered_count", 0
                )

        return {
            "unmapped_count": total_unmapped,
            "noise_filtered_count": total_noise,
        }

    def _find_missing(
        self,
        best: dict[tuple[str, str], object],
        latest_period: str | None,
        periods: list[str],
        pipeline_ctx: dict[str, int],
    ) -> list[MissingItem]:
        if not latest_period:
            return []

        missing = []
        has_unmapped = pipeline_ctx.get("unmapped_count", 0) > 0
        has_noise = pipeline_ctx.get("noise_filtered_count", 0) > 0

        present_metrics = {
            metric for (metric, period) in best if period == latest_period
        }

        # Income statement completeness
        for m in sorted(INCOME_METRICS):
            if m not in present_metrics:
                mtype = self._classify_missing_type(
                    m, has_unmapped, has_noise, "income"
                )
                missing.append(
                    MissingItem(
                        metric=m,
                        period=latest_period,
                        reason=self._missing_reason(
                            m, latest_period, mtype, pipeline_ctx
                        ),
                        type=mtype,
                    )
                )

        # Balance sheet completeness
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
            mtype = self._classify_missing_type(
                StandardMetric.CASH.value, has_unmapped, has_noise, "cash"
            )
            missing.append(
                MissingItem(
                    metric=StandardMetric.CASH.value,
                    period=latest_period,
                    reason=self._missing_reason(
                        StandardMetric.CASH.value,
                        latest_period,
                        mtype,
                        pipeline_ctx,
                    ),
                    type=mtype,
                )
            )

        # Period regression
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

    def _classify_missing_type(
        self,
        metric: str,
        has_unmapped: bool,
        has_noise: bool,
        category: str,
    ) -> str:
        """Determine why a metric is missing based on pipeline context."""
        # If the pipeline had significant unmapped labels, this metric
        # may have existed in the file but failed to map
        if has_unmapped:
            return "failed_mapping"
        if has_noise:
            return "filtered_noise"
        return "absent_in_latest"

    def _missing_reason(
        self,
        metric: str,
        period: str,
        mtype: str,
        ctx: dict[str, int],
    ) -> str:
        """Build human-readable reason for a missing metric."""
        if mtype == "failed_mapping":
            n = ctx.get("unmapped_count", 0)
            return (
                f"No {metric} found for {period} — "
                f"{n} labels failed to map across uploads"
            )
        if mtype == "filtered_noise":
            n = ctx.get("noise_filtered_count", 0)
            return (
                f"No {metric} found for {period} — "
                f"{n} values filtered as noise across uploads"
            )
        return f"No {metric} found for {period}"

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
            if r.confidence_total is not None
            and r.confidence_total < 0.5
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

        scores = [
            r.confidence_total
            for r in rows
            if r.confidence_total is not None
            and r.status != "REJECTED"
        ]
        raw_avg = sum(scores) / len(scores) if scores else 0.0

        active_count = len(scores)
        if active_count > 0:
            failure_rate = (sanity_fails + hard_blocked) / active_count
            penalty = min(failure_rate * 0.3, 0.3)
            overall = max(raw_avg - penalty, 0.0)
        else:
            overall = 0.0

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
