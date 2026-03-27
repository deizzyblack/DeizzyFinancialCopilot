from datetime import date

from src.core.enums import PeriodType
from src.period.service import PeriodNormalizer


class TestPeriodNormalizer:
    def setup_method(self):
        self.normalizer = PeriodNormalizer()

    def test_quarter_format_q1_2025(self):
        result = self.normalizer.normalize("Q1 2025")
        assert result.normalized_period == "Q1-2025"
        assert result.period_type == PeriodType.QUARTER
        assert result.period_end_date == date(2025, 3, 31)

    def test_quarter_format_2q25(self):
        result = self.normalizer.normalize("2Q25")
        assert result.normalized_period == "Q2-2025"
        assert result.period_type == PeriodType.QUARTER

    def test_half_year_h1_2025(self):
        result = self.normalizer.normalize("H1 2025")
        assert result.normalized_period == "H1-2025"
        assert result.period_type == PeriodType.HALF

    def test_half_year_h2(self):
        result = self.normalizer.normalize("H2-2025")
        assert result.normalized_period == "H2-2025"
        assert result.period_type == PeriodType.HALF

    def test_date_format_dd_mm_yyyy(self):
        result = self.normalizer.normalize("30.06.2025")
        assert result.normalized_period == "Q2-2025"
        assert result.period_type == PeriodType.QUARTER
        assert result.period_end_date == date(2025, 6, 30)

    def test_date_format_iso(self):
        result = self.normalizer.normalize("2025-03-31")
        assert result.normalized_period == "Q1-2025"
        assert result.period_type == PeriodType.QUARTER

    def test_fy_format(self):
        result = self.normalizer.normalize("FY2025")
        assert result.normalized_period == "FY-2025"
        assert result.period_type == PeriodType.FULL_YEAR

    def test_ytd_format(self):
        result = self.normalizer.normalize("YTD 2025")
        assert result.normalized_period == "YTD-2025"
        assert result.period_type == PeriodType.YTD

    def test_month_abbreviation(self):
        result = self.normalizer.normalize("Jun-25")
        assert result.normalized_period == "Q2-2025"
        assert result.period_type == PeriodType.QUARTER

    def test_unknown_period(self):
        result = self.normalizer.normalize("gibberish")
        assert result.period_type == PeriodType.UNKNOWN
        assert result.confidence == 0.0

    def test_quarter_not_equal_half(self):
        q2 = self.normalizer.normalize("Q2 2025")
        h1 = self.normalizer.normalize("H1 2025")
        assert q2.period_type != h1.period_type
        assert q2.normalized_period != h1.normalized_period

    def test_year_only_fallback(self):
        result = self.normalizer.normalize("2025")
        assert result.normalized_period == "FY-2025"
        assert result.period_type == PeriodType.FULL_YEAR
        assert result.confidence == 0.5
