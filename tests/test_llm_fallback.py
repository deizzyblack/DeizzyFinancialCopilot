"""Tests for LLM fallback in mapping and period normalization."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.enums import MappingMethod, PeriodType
from src.core.llm_client import LLMClient, LLMMappingResult, LLMPeriodResult
from src.mapping.service import SemanticMapper
from src.models.database import Base
from src.period.service import PeriodNormalizer


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def mock_llm():
    return MagicMock(spec=LLMClient)


# --- SemanticMapper LLM fallback ---


class TestMappingLLMFallback:
    def test_llm_used_when_rules_fail(self, db_session, mock_llm):
        mock_llm.map_metric.return_value = LLMMappingResult(
            metric="Revenue", confidence=0.9
        )
        mapper = SemanticMapper(db_session, llm_client=mock_llm)

        result = mapper.map_label("Umsatzerlöse")

        assert result.metric is not None
        assert result.metric.value == "Revenue"
        assert result.method == MappingMethod.LLM_FALLBACK
        assert result.mapping_score == pytest.approx(0.72)  # 0.9 * 0.8
        mock_llm.map_metric.assert_called_once_with("Umsatzerlöse")

    def test_llm_not_called_when_rules_match(self, db_session, mock_llm):
        mapper = SemanticMapper(db_session, llm_client=mock_llm)

        result = mapper.map_label("Revenue")

        assert result.method == MappingMethod.RULE_BASED
        mock_llm.map_metric.assert_not_called()

    def test_llm_returns_none_falls_through(self, db_session, mock_llm):
        mock_llm.map_metric.return_value = None
        mapper = SemanticMapper(db_session, llm_client=mock_llm)

        result = mapper.map_label("Gibberish XYZ 123")

        assert result.metric is None
        assert result.mapping_score == 0.0

    def test_llm_returns_no_metric_falls_through(self, db_session, mock_llm):
        mock_llm.map_metric.return_value = LLMMappingResult(
            metric=None, confidence=0.0
        )
        mapper = SemanticMapper(db_session, llm_client=mock_llm)

        result = mapper.map_label("Gibberish XYZ 123")

        assert result.metric is None
        assert result.mapping_score == 0.0

    def test_llm_invalid_metric_falls_through(self, db_session, mock_llm):
        mock_llm.map_metric.return_value = LLMMappingResult(
            metric="NotAMetric", confidence=0.9
        )
        mapper = SemanticMapper(db_session, llm_client=mock_llm)

        result = mapper.map_label("Gibberish XYZ 123")

        assert result.metric is None
        assert result.mapping_score == 0.0

    def test_no_llm_client_skips_fallback(self, db_session):
        mapper = SemanticMapper(db_session)

        result = mapper.map_label("Gibberish XYZ 123")

        assert result.metric is None
        assert result.mapping_score == 0.0

    def test_llm_confidence_capped(self, db_session, mock_llm):
        mock_llm.map_metric.return_value = LLMMappingResult(
            metric="EBITDA", confidence=1.0
        )
        mapper = SemanticMapper(db_session, llm_client=mock_llm)

        result = mapper.map_label("Betriebsergebnis vor Abschreibungen")

        assert result.mapping_score == pytest.approx(0.8)  # 1.0 * 0.8


# --- PeriodNormalizer LLM fallback ---


class TestPeriodLLMFallback:
    def test_llm_used_when_regex_fails(self, mock_llm):
        mock_llm.normalize_period.return_value = LLMPeriodResult(
            period="Q3-2025", period_type="QUARTER", confidence=0.85
        )
        normalizer = PeriodNormalizer(llm_client=mock_llm)

        result = normalizer.normalize("Drittes Quartal zweitausendfünfundzwanzig")

        assert result.normalized_period == "Q3-2025"
        assert result.period_type == PeriodType.QUARTER
        assert result.confidence == pytest.approx(0.68)  # 0.85 * 0.8

    def test_llm_not_called_when_regex_matches(self, mock_llm):
        normalizer = PeriodNormalizer(llm_client=mock_llm)

        result = normalizer.normalize("Q1-2025")

        assert result.period_type == PeriodType.QUARTER
        mock_llm.normalize_period.assert_not_called()

    def test_llm_returns_none_falls_through(self, mock_llm):
        mock_llm.normalize_period.return_value = None
        normalizer = PeriodNormalizer(llm_client=mock_llm)

        result = normalizer.normalize("complete nonsense")

        assert result.period_type == PeriodType.UNKNOWN
        assert result.confidence == 0.0

    def test_llm_invalid_period_type_falls_through(self, mock_llm):
        mock_llm.normalize_period.return_value = LLMPeriodResult(
            period="Q1-2025", period_type="INVALID", confidence=0.9
        )
        normalizer = PeriodNormalizer(llm_client=mock_llm)

        result = normalizer.normalize("complete nonsense")

        assert result.period_type == PeriodType.UNKNOWN

    def test_no_llm_client_skips_fallback(self):
        normalizer = PeriodNormalizer()

        result = normalizer.normalize("complete nonsense")

        assert result.period_type == PeriodType.UNKNOWN
        assert result.confidence == 0.0

    def test_llm_missing_fields_falls_through(self, mock_llm):
        mock_llm.normalize_period.return_value = LLMPeriodResult(
            period=None, period_type=None, confidence=0.5
        )
        normalizer = PeriodNormalizer(llm_client=mock_llm)

        result = normalizer.normalize("???")

        assert result.period_type == PeriodType.UNKNOWN


# --- LLMClient unit tests (no HTTP) ---


class TestLLMClientDisabled:
    def test_disabled_returns_none(self):
        client = LLMClient(enabled=False)
        assert client.map_metric("Revenue") is None
        assert client.normalize_period("Q1 2025") is None

    def test_missing_config_returns_none(self):
        client = LLMClient(enabled=True, api_url="", api_key="")
        assert client.map_metric("Revenue") is None
