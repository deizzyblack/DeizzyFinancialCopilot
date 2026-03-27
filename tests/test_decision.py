from src.core.enums import DecisionType
from src.core.schemas import ConfidenceScore
from src.decision.service import DecisionEngine


class TestDecisionEngine:
    def test_auto_ready_high_confidence(self):
        engine = DecisionEngine()
        conf = ConfidenceScore(
            extraction=0.9,
            mapping=0.95,
            sanity=1.0,
            source=0.85,
            historical=0.9,
            total=0.92,
        )
        result = engine.decide(conf)
        assert result.decision == DecisionType.AUTO_READY

    def test_review_required_medium(self):
        engine = DecisionEngine()
        conf = ConfidenceScore(
            extraction=0.7,
            mapping=0.6,
            sanity=1.0,
            source=0.7,
            historical=0.5,
            total=0.68,
        )
        result = engine.decide(conf)
        assert result.decision == DecisionType.REVIEW_REQUIRED

    def test_flag_low_confidence(self):
        engine = DecisionEngine()
        conf = ConfidenceScore(
            extraction=0.3,
            mapping=0.2,
            sanity=0.0,
            source=0.4,
            historical=0.3,
            total=0.25,
        )
        result = engine.decide(conf)
        assert result.decision == DecisionType.FLAG

    def test_hard_blocked_always_flag(self):
        engine = DecisionEngine()
        conf = ConfidenceScore(
            extraction=0.9,
            mapping=0.95,
            sanity=0.0,
            source=0.85,
            historical=0.9,
            total=0.70,
            hard_blocked=True,
            block_reasons=["Sanity critical: test"],
        )
        result = engine.decide(conf)
        assert result.decision == DecisionType.FLAG
