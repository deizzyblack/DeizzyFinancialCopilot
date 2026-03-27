from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.core.enums import MappingMethod, StandardMetric
from src.core.llm_client import LLMClient
from src.core.schemas import MappingResult
from src.models.database import MappingMemory

SYNONYM_MAP: dict[str, StandardMetric] = {
    "revenue": StandardMetric.REVENUE,
    "net sales": StandardMetric.REVENUE,
    "total revenue": StandardMetric.REVENUE,
    "sales": StandardMetric.REVENUE,
    "net revenue": StandardMetric.REVENUE,
    "turnover": StandardMetric.REVENUE,
    "total sales": StandardMetric.REVENUE,
    "gross revenue": StandardMetric.REVENUE,
    "ebitda": StandardMetric.EBITDA,
    "operating profit before depreciation": StandardMetric.EBITDA,
    "earnings before interest tax depreciation amortization": StandardMetric.EBITDA,
    "net income": StandardMetric.NET_INCOME,
    "net profit": StandardMetric.NET_INCOME,
    "net earnings": StandardMetric.NET_INCOME,
    "profit after tax": StandardMetric.NET_INCOME,
    "net result": StandardMetric.NET_INCOME,
    "bottom line": StandardMetric.NET_INCOME,
    "profit for the period": StandardMetric.NET_INCOME,
    "cash": StandardMetric.CASH,
    "cash and cash equivalents": StandardMetric.CASH,
    "cash & cash equivalents": StandardMetric.CASH,
    "total cash": StandardMetric.CASH,
    "total assets": StandardMetric.ASSETS,
    "assets": StandardMetric.ASSETS,
    "total liabilities": StandardMetric.LIABILITIES,
    "liabilities": StandardMetric.LIABILITIES,
    "total debt": StandardMetric.LIABILITIES,
    "total equity": StandardMetric.EQUITY,
    "equity": StandardMetric.EQUITY,
    "shareholders equity": StandardMetric.EQUITY,
    "shareholders' equity": StandardMetric.EQUITY,
    "stockholders equity": StandardMetric.EQUITY,
    "book value": StandardMetric.EQUITY,
}


class SemanticMapper:
    def __init__(self, session: Session, llm_client: LLMClient | None = None):
        self.session = session
        self.llm_client = llm_client

    def add_company_mapping(
        self, company_id: str, label: str, metric: StandardMetric
    ) -> None:
        normalized = label.lower().strip()

        existing = (
            self.session.query(MappingMemory)
            .filter(
                MappingMemory.company_id == company_id,
                MappingMemory.original_label == normalized,
                MappingMemory.mapped_metric == metric.value,
            )
            .first()
        )

        if existing:
            existing.approved = "true"
            existing.approve_count = (existing.approve_count or 0) + 1
            existing.updated_at = datetime.now(UTC)
        else:
            row = MappingMemory(
                company_id=company_id,
                original_label=normalized,
                mapped_metric=metric.value,
                approved="true",
                approve_count=1,
                reject_count=0,
            )
            self.session.add(row)

        self.session.flush()

    def reject_mapping(
        self, company_id: str, label: str, metric: StandardMetric
    ) -> None:
        """Record a rejected mapping as a negative signal. Append-only."""
        normalized = label.lower().strip()

        existing = (
            self.session.query(MappingMemory)
            .filter(
                MappingMemory.company_id == company_id,
                MappingMemory.original_label == normalized,
                MappingMemory.mapped_metric == metric.value,
            )
            .first()
        )

        if existing:
            existing.approved = "rejected"
            existing.reject_count = (existing.reject_count or 0) + 1
            existing.updated_at = datetime.now(UTC)
        else:
            row = MappingMemory(
                company_id=company_id,
                original_label=normalized,
                mapped_metric=metric.value,
                approved="rejected",
                approve_count=0,
                reject_count=1,
            )
            self.session.add(row)

        self.session.flush()

    def map_label(self, raw_label: str, company_id: str | None = None) -> MappingResult:
        normalized = raw_label.lower().strip()

        if company_id:
            row = (
                self.session.query(MappingMemory)
                .filter(
                    MappingMemory.company_id == company_id,
                    MappingMemory.original_label == normalized,
                    MappingMemory.approved != "rejected",
                )
                .order_by(MappingMemory.approve_count.desc())
                .first()
            )
            if row:
                try:
                    metric = StandardMetric(row.mapped_metric)
                except ValueError:
                    metric = None
                if metric:
                    score = self._approval_score(row)
                    return MappingResult(
                        metric=metric,
                        mapping_score=score,
                        method=MappingMethod.COMPANY_APPROVED,
                        reason=(
                            f"Company-approved mapping: {raw_label} -> {metric.value} "
                            f"(approved {row.approve_count or 0}x)"
                        ),
                    )

        if normalized in SYNONYM_MAP:
            metric = SYNONYM_MAP[normalized]
            boost = self._rule_boost(normalized, metric, company_id)
            return MappingResult(
                metric=metric,
                mapping_score=min(0.95 + boost, 1.0),
                method=MappingMethod.RULE_BASED,
                reason=f"Rule-based synonym: {raw_label} -> {metric.value}",
            )

        for synonym, metric in SYNONYM_MAP.items():
            if synonym in normalized or normalized in synonym:
                boost = self._rule_boost(normalized, metric, company_id)
                return MappingResult(
                    metric=metric,
                    mapping_score=min(0.75 + boost, 1.0),
                    method=MappingMethod.RULE_BASED,
                    reason=f"Partial match: {raw_label} ~ {synonym} -> {metric.value}",
                )

        if self.llm_client:
            llm_result = self.llm_client.map_metric(raw_label)
            if llm_result and llm_result.metric:
                try:
                    metric = StandardMetric(llm_result.metric)
                except ValueError:
                    metric = None
                if metric:
                    return MappingResult(
                        metric=metric,
                        mapping_score=llm_result.confidence * 0.8,
                        method=MappingMethod.LLM_FALLBACK,
                        reason=f"LLM fallback: {raw_label} -> {metric.value}",
                    )

        return MappingResult(
            metric=None,
            mapping_score=0.0,
            method=MappingMethod.RULE_BASED,
            reason=f"No mapping found for: {raw_label}",
        )

    def _approval_score(self, row: MappingMemory) -> float:
        """Score based on approval history. More approvals → higher confidence."""
        approvals = row.approve_count or 0
        if approvals >= 3:
            return 1.0
        if approvals >= 1:
            return 0.95
        return 0.85

    def _rule_boost(
        self, label: str, metric: StandardMetric, company_id: str | None
    ) -> float:
        """Boost rule-based score if prior approvals exist for this label→metric."""
        if not company_id:
            return 0.0

        row = (
            self.session.query(MappingMemory)
            .filter(
                MappingMemory.company_id == company_id,
                MappingMemory.original_label == label,
                MappingMemory.mapped_metric == metric.value,
                MappingMemory.approved == "true",
            )
            .first()
        )

        if row and (row.approve_count or 0) > 0:
            return 0.05
        return 0.0
