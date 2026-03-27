from sqlalchemy.orm import Session

from src.core.enums import MappingMethod, StandardMetric
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
    def __init__(self, session: Session):
        self.session = session

    def add_company_mapping(
        self, company_id: str, label: str, metric: StandardMetric
    ) -> None:
        normalized = label.lower().strip()

        existing = (
            self.session.query(MappingMemory)
            .filter(
                MappingMemory.company_id == company_id,
                MappingMemory.original_label == normalized,
            )
            .first()
        )

        if existing:
            existing.mapped_metric = metric.value
            existing.approved = "true"
        else:
            row = MappingMemory(
                company_id=company_id,
                original_label=normalized,
                mapped_metric=metric.value,
                approved="true",
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
                )
                .first()
            )
            if row:
                try:
                    metric = StandardMetric(row.mapped_metric)
                except ValueError:
                    metric = None
                if metric:
                    return MappingResult(
                        metric=metric,
                        mapping_score=1.0,
                        method=MappingMethod.COMPANY_APPROVED,
                        reason=f"Company-approved mapping: {raw_label} -> {metric.value}",
                    )

        if normalized in SYNONYM_MAP:
            metric = SYNONYM_MAP[normalized]
            return MappingResult(
                metric=metric,
                mapping_score=0.95,
                method=MappingMethod.RULE_BASED,
                reason=f"Rule-based synonym: {raw_label} -> {metric.value}",
            )

        for synonym, metric in SYNONYM_MAP.items():
            if synonym in normalized or normalized in synonym:
                return MappingResult(
                    metric=metric,
                    mapping_score=0.75,
                    method=MappingMethod.RULE_BASED,
                    reason=f"Partial match: {raw_label} ~ {synonym} -> {metric.value}",
                )

        return MappingResult(
            metric=None,
            mapping_score=0.0,
            method=MappingMethod.RULE_BASED,
            reason=f"No mapping found for: {raw_label}",
        )
