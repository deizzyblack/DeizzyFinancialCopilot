import uuid

from src.core.enums import ActionType, ChangeType, DecisionType
from src.core.schemas import (
    ActionRecommendation,
    ChangeDetectionResult,
    DecisionResult,
)


class ActionGenerator:
    def generate(
        self,
        decision: DecisionResult,
        change: ChangeDetectionResult,
        record_id: uuid.UUID | None = None,
    ) -> ActionRecommendation:
        if change.change_type == ChangeType.DUPLICATE:
            return ActionRecommendation(
                action=ActionType.IGNORE,
                reason="Duplicate value — no change needed",
                record_id=record_id,
                details={"change_type": change.change_type.value},
            )

        if decision.decision == DecisionType.AUTO_READY:
            return ActionRecommendation(
                action=ActionType.UPDATE,
                reason=decision.reason,
                record_id=record_id,
                details={
                    "confidence": decision.confidence.total,
                    "change_type": change.change_type.value,
                },
            )

        if decision.decision == DecisionType.REVIEW_REQUIRED:
            return ActionRecommendation(
                action=ActionType.REVIEW,
                reason=decision.reason,
                record_id=record_id,
                details={
                    "confidence": decision.confidence.total,
                    "change_type": change.change_type.value,
                    "block_reasons": decision.confidence.block_reasons,
                },
            )

        return ActionRecommendation(
            action=ActionType.INVESTIGATE,
            reason=decision.reason,
            record_id=record_id,
            details={
                "confidence": decision.confidence.total,
                "block_reasons": decision.confidence.block_reasons,
            },
        )
