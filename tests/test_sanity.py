import uuid

from src.core.enums import PeriodType, StandardMetric
from src.core.schemas import CandidateRecord
from src.sanity.service import SanityEngine
from src.storage.service import StorageService


def _make_record(metric: StandardMetric, value: float, period: str = "Q2-2025") -> CandidateRecord:
    return CandidateRecord(
        company_id="ACME",
        metric=metric,
        value=value,
        raw_label="test",
        period=period,
        period_type=PeriodType.QUARTER,
        file_id=uuid.uuid4(),
        sheet="Sheet1",
        cell="B2",
    )


class TestSanityEngine:
    def test_valid_record(self, db_session):
        storage = StorageService(db_session)
        engine = SanityEngine(storage)
        record = _make_record(StandardMetric.REVENUE, 1000000)
        result = engine.check(record)
        assert result.passed is True

    def test_negative_revenue(self, db_session):
        storage = StorageService(db_session)
        engine = SanityEngine(storage)
        record = _make_record(StandardMetric.REVENUE, -500)
        result = engine.check(record)
        assert result.passed is False
        assert any("negative" in i.lower() for i in result.issues)

    def test_ebitda_exceeds_revenue(self, db_session):
        storage = StorageService(db_session)
        engine = SanityEngine(storage)

        revenue_record = _make_record(StandardMetric.REVENUE, 1000)
        storage.store(revenue_record)

        ebitda_record = _make_record(StandardMetric.EBITDA, 2000)
        result = engine.check(ebitda_record)
        assert result.passed is False
        assert any("exceeds" in i.lower() for i in result.issues)

    def test_balance_sheet_mismatch(self, db_session):
        storage = StorageService(db_session)
        engine = SanityEngine(storage)

        storage.store(_make_record(StandardMetric.ASSETS, 1000))
        storage.store(_make_record(StandardMetric.LIABILITIES, 400))

        equity_record = _make_record(StandardMetric.EQUITY, 300)
        result = engine.check(equity_record)
        assert result.passed is False
        assert any("mismatch" in i.lower() for i in result.issues)

    def test_balance_sheet_valid(self, db_session):
        storage = StorageService(db_session)
        engine = SanityEngine(storage)

        storage.store(_make_record(StandardMetric.ASSETS, 1000))
        storage.store(_make_record(StandardMetric.LIABILITIES, 600))

        equity_record = _make_record(StandardMetric.EQUITY, 400)
        result = engine.check(equity_record)
        assert result.passed is True
