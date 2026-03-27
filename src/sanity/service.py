from src.core.enums import StandardMetric
from src.core.schemas import CandidateRecord, SanityResult
from src.storage.service import StorageService


class SanityEngine:
    """Deterministic validation rules. NO AI allowed."""

    def __init__(self, storage: StorageService):
        self.storage = storage

    def check(self, record: CandidateRecord) -> SanityResult:
        issues = []

        issues.extend(self._check_negative_revenue(record))
        issues.extend(self._check_ebitda_vs_revenue(record))
        issues.extend(self._check_balance_sheet_equation(record))

        return SanityResult(passed=len(issues) == 0, issues=issues)

    def _check_negative_revenue(self, record: CandidateRecord) -> list[str]:
        if record.metric == StandardMetric.REVENUE and record.value < 0:
            return ["Revenue cannot be negative"]
        return []

    def _check_ebitda_vs_revenue(self, record: CandidateRecord) -> list[str]:
        if record.metric != StandardMetric.EBITDA:
            return []

        records = self.storage.get_records_for_period(
            record.company_id, record.period
        )
        for r in records:
            if r.record.metric == StandardMetric.REVENUE:
                if abs(record.value) > abs(r.record.value) and record.value > 0:
                    return [
                        f"EBITDA ({record.value}) exceeds Revenue ({r.record.value})"
                    ]
        return []

    def _check_balance_sheet_equation(self, record: CandidateRecord) -> list[str]:
        if record.metric not in (
            StandardMetric.ASSETS,
            StandardMetric.LIABILITIES,
            StandardMetric.EQUITY,
        ):
            return []

        records = self.storage.get_records_for_period(
            record.company_id, record.period
        )

        values: dict[StandardMetric, float] = {}
        for r in records:
            if r.record.metric in (
                StandardMetric.ASSETS,
                StandardMetric.LIABILITIES,
                StandardMetric.EQUITY,
            ):
                values[r.record.metric] = r.record.value

        values[record.metric] = record.value

        if len(values) == 3:
            assets = values.get(StandardMetric.ASSETS, 0)
            liabilities = values.get(StandardMetric.LIABILITIES, 0)
            equity = values.get(StandardMetric.EQUITY, 0)
            tolerance = max(abs(assets) * 0.01, 1.0)
            if abs(assets - (liabilities + equity)) > tolerance:
                return [
                    f"Balance sheet mismatch: Assets ({assets}) != "
                    f"Liabilities ({liabilities}) + Equity ({equity})"
                ]

        return []
