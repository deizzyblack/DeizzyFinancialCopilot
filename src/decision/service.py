from src.core.config import settings
from src.core.enums import DecisionType
from src.core.schemas import ConfidenceScore, DecisionResult


class DecisionEngine:
    def decide(self, confidence: ConfidenceScore) -> DecisionResult:
        if confidence.hard_blocked:
            return DecisionResult(
                decision=DecisionType.FLAG,
                confidence=confidence,
                reason=f"Hard blocked: {'; '.join(confidence.block_reasons)}",
            )

        if confidence.total >= settings.auto_approve_threshold:
            return DecisionResult(
                decision=DecisionType.AUTO_READY,
                confidence=confidence,
                reason=f"High confidence ({confidence.total:.2f}) - auto-approve ready",
            )

        if confidence.total >= settings.review_threshold:
            return DecisionResult(
                decision=DecisionType.REVIEW_REQUIRED,
                confidence=confidence,
                reason=f"Medium confidence ({confidence.total:.2f}) - review required",
            )

        return DecisionResult(
            decision=DecisionType.FLAG,
            confidence=confidence,
            reason=f"Low confidence ({confidence.total:.2f}) - flagged for investigation",
        )
