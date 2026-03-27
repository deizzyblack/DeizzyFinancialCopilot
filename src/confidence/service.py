from src.core.enums import ChangeType, PeriodType
from src.core.schemas import (
    CandidateRecord,
    ChangeDetectionResult,
    ConfidenceScore,
    MappingResult,
    PeriodResult,
    SanityResult,
)

WEIGHTS = {
    "extraction": 0.25,
    "mapping": 0.20,
    "sanity": 0.25,
    "source": 0.15,
    "historical": 0.15,
}


class ConfidenceEngine:
    def score(
        self,
        record: CandidateRecord,
        mapping: MappingResult,
        period: PeriodResult,
        sanity: SanityResult,
        source_score: float,
        change: ChangeDetectionResult,
    ) -> ConfidenceScore:
        block_reasons = []

        extraction_score = self._extraction_confidence(record, period)
        mapping_score = mapping.mapping_score
        sanity_score = 1.0 if sanity.passed else 0.0
        historical_score = self._historical_confidence(change)

        if not sanity.passed:
            for issue in sanity.issues:
                if any(
                    kw in issue.lower()
                    for kw in ["mismatch", "exceeds", "negative", "error"]
                ):
                    block_reasons.append(f"Sanity critical: {issue}")

        if period.period_type == PeriodType.UNKNOWN:
            block_reasons.append("Missing/unknown period")

        if mapping.metric is None:
            block_reasons.append("Ambiguous metric mapping")

        total = (
            WEIGHTS["extraction"] * extraction_score
            + WEIGHTS["mapping"] * mapping_score
            + WEIGHTS["sanity"] * sanity_score
            + WEIGHTS["source"] * source_score
            + WEIGHTS["historical"] * historical_score
        )

        return ConfidenceScore(
            extraction=round(extraction_score, 3),
            mapping=round(mapping_score, 3),
            sanity=round(sanity_score, 3),
            source=round(source_score, 3),
            historical=round(historical_score, 3),
            total=round(total, 3),
            hard_blocked=len(block_reasons) > 0,
            block_reasons=block_reasons,
        )

    def _extraction_confidence(
        self, record: CandidateRecord, period: PeriodResult
    ) -> float:
        score = 0.5
        if record.value != 0:
            score += 0.2
        if period.confidence > 0.8:
            score += 0.3
        elif period.confidence > 0.5:
            score += 0.15
        return min(score, 1.0)

    def _historical_confidence(self, change: ChangeDetectionResult) -> float:
        if change.change_type == ChangeType.NEW:
            return 0.7
        if change.change_type == ChangeType.DUPLICATE:
            return 1.0
        if change.change_type == ChangeType.REVISION:
            if change.old_value and change.old_value != 0:
                pct_change = abs(change.diff or 0) / abs(change.old_value)
                if pct_change < 0.05:
                    return 0.9
                if pct_change < 0.2:
                    return 0.7
                if pct_change < 0.5:
                    return 0.5
                return 0.3
            return 0.5
        return 0.5
