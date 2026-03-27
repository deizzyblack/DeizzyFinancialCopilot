import re
from datetime import date

from src.core.enums import PeriodType
from src.core.llm_client import LLMClient
from src.core.schemas import PeriodResult

QUARTER_END_MONTHS = {1: 3, 2: 6, 3: 9, 4: 12}
QUARTER_END_DAYS = {3: 31, 6: 30, 9: 30, 12: 31}
HALF_END_MONTHS = {1: 6, 2: 12}

QUARTER_PATTERNS = [
    (r"[Qq](\d)\s*[-/]?\s*(\d{4})", "Q_YEAR"),
    (r"(\d)[Qq]\s*[-/]?\s*(\d{2,4})", "NQ_YEAR"),
    (r"[Qq](\d)\s*(\d{2})", "Q_YY"),
]

HALF_PATTERNS = [
    (r"[Hh](\d)\s*[-/]?\s*(\d{4})", "H_YEAR"),
    (r"[Hh](\d)\s*[-/]?\s*(\d{2})", "H_YY"),
    (r"(\d)[Hh]\s*[-/]?\s*(\d{2,4})", "NH_YEAR"),
]

DATE_PATTERNS = [
    (r"(\d{2})\.(\d{2})\.(\d{4})", "DD.MM.YYYY"),
    (r"(\d{4})-(\d{2})-(\d{2})", "YYYY-MM-DD"),
    (r"(\d{2})/(\d{2})/(\d{4})", "MM/DD/YYYY"),
]

FY_PATTERNS = [
    (r"[Ff][Yy]\s*[-/]?\s*(\d{4})", "FY_YEAR"),
    (r"[Ff][Yy]\s*[-/]?\s*(\d{2})", "FY_YY"),
]

YTD_PATTERNS = [
    (r"[Yy][Tt][Dd]\s*[-/]?\s*(\d{4})", "YTD_YEAR"),
]

MONTH_ABBREV = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _expand_year(y: str) -> int:
    yr = int(y)
    if yr < 100:
        yr += 2000
    return yr


def _quarter_from_month(month: int) -> int:
    return (month - 1) // 3 + 1


def _quarter_end_date(quarter: int, year: int) -> date:
    m = QUARTER_END_MONTHS[quarter]
    d = QUARTER_END_DAYS[m]
    return date(year, m, d)


PERIOD_TYPE_MAP = {
    "QUARTER": PeriodType.QUARTER,
    "HALF": PeriodType.HALF,
    "YTD": PeriodType.YTD,
    "FULL_YEAR": PeriodType.FULL_YEAR,
}


class PeriodNormalizer:
    def __init__(self, llm_client: LLMClient | None = None):
        self.llm_client = llm_client

    def normalize(self, raw_period: str) -> PeriodResult:
        text = str(raw_period).strip()

        for pattern, _ in QUARTER_PATTERNS:
            m = re.search(pattern, text)
            if m:
                groups = m.groups()
                if _.startswith("NQ"):
                    q, y = int(groups[0]), _expand_year(groups[1])
                else:
                    q, y = int(groups[0]), _expand_year(groups[1])
                if 1 <= q <= 4:
                    return PeriodResult(
                        raw_period=text,
                        normalized_period=f"Q{q}-{y}",
                        period_type=PeriodType.QUARTER,
                        period_end_date=_quarter_end_date(q, y),
                        confidence=0.95,
                    )

        for pattern, _ in HALF_PATTERNS:
            m = re.search(pattern, text)
            if m:
                groups = m.groups()
                if _.startswith("NH"):
                    h, y = int(groups[0]), _expand_year(groups[1])
                else:
                    h, y = int(groups[0]), _expand_year(groups[1])
                if h in (1, 2):
                    end_m = HALF_END_MONTHS[h]
                    end_d = QUARTER_END_DAYS.get(end_m, 30)
                    return PeriodResult(
                        raw_period=text,
                        normalized_period=f"H{h}-{y}",
                        period_type=PeriodType.HALF,
                        period_end_date=date(y, end_m, end_d),
                        confidence=0.9,
                    )

        for pattern, fmt in DATE_PATTERNS:
            m = re.search(pattern, text)
            if m:
                groups = m.groups()
                if fmt == "DD.MM.YYYY":
                    day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                elif fmt == "YYYY-MM-DD":
                    year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                else:
                    month, day, year = int(groups[0]), int(groups[1]), int(groups[2])

                q = _quarter_from_month(month)
                try:
                    end_date = date(year, month, day)
                except ValueError:
                    continue
                return PeriodResult(
                    raw_period=text,
                    normalized_period=f"Q{q}-{year}",
                    period_type=PeriodType.QUARTER,
                    period_end_date=end_date,
                    confidence=0.9,
                )

        for pattern, _ in FY_PATTERNS:
            m = re.search(pattern, text)
            if m:
                y = _expand_year(m.group(1))
                return PeriodResult(
                    raw_period=text,
                    normalized_period=f"FY-{y}",
                    period_type=PeriodType.FULL_YEAR,
                    period_end_date=date(y, 12, 31),
                    confidence=0.9,
                )

        for pattern, _ in YTD_PATTERNS:
            m = re.search(pattern, text)
            if m:
                y = _expand_year(m.group(1))
                return PeriodResult(
                    raw_period=text,
                    normalized_period=f"YTD-{y}",
                    period_type=PeriodType.YTD,
                    period_end_date=None,
                    confidence=0.8,
                )

        month_pattern = r"([A-Za-z]{3})\s*[-/]?\s*(\d{2,4})"
        m = re.search(month_pattern, text)
        if m:
            abbrev = m.group(1).lower()
            if abbrev in MONTH_ABBREV:
                month = MONTH_ABBREV[abbrev]
                year = _expand_year(m.group(2))
                q = _quarter_from_month(month)
                return PeriodResult(
                    raw_period=text,
                    normalized_period=f"Q{q}-{year}",
                    period_type=PeriodType.QUARTER,
                    period_end_date=_quarter_end_date(q, year),
                    confidence=0.8,
                )

        year_only = re.search(r"\b(20\d{2})\b", text)
        if year_only:
            y = int(year_only.group(1))
            return PeriodResult(
                raw_period=text,
                normalized_period=f"FY-{y}",
                period_type=PeriodType.FULL_YEAR,
                period_end_date=date(y, 12, 31),
                confidence=0.5,
            )

        if self.llm_client:
            llm_result = self.llm_client.normalize_period(text)
            if llm_result and llm_result.period and llm_result.period_type:
                pt = PERIOD_TYPE_MAP.get(llm_result.period_type)
                if pt:
                    return PeriodResult(
                        raw_period=text,
                        normalized_period=llm_result.period,
                        period_type=pt,
                        period_end_date=None,
                        confidence=llm_result.confidence * 0.8,
                    )

        return PeriodResult(
            raw_period=text,
            normalized_period="UNKNOWN",
            period_type=PeriodType.UNKNOWN,
            period_end_date=None,
            confidence=0.0,
        )
