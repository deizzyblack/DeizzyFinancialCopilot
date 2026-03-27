from datetime import datetime
from pathlib import Path

import openpyxl

from src.core.schemas import RawExtraction

FINANCIAL_KEYWORDS = [
    "income",
    "revenue",
    "sales",
    "ebitda",
    "profit",
    "loss",
    "balance",
    "asset",
    "liabilit",
    "equity",
    "cash",
    "expense",
    "operating",
    "financial",
    "statement",
    "p&l",
]


def _is_financial_sheet(sheet_name: str) -> bool:
    name_lower = sheet_name.lower()
    return any(kw in name_lower for kw in FINANCIAL_KEYWORDS)


def _cell_ref(row: int, col: int) -> str:
    col_letter = openpyxl.utils.get_column_letter(col)
    return f"{col_letter}{row}"


def _is_numeric(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace(" ", "").strip()
        try:
            float(cleaned)
            return True
        except ValueError:
            return False
    return False


def _to_numeric(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace(" ", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _is_header_value(value) -> bool:
    """Check if a value looks like a column header (date, year, period label)."""
    if value is None:
        return False
    if isinstance(value, datetime):
        return True
    s = str(value).strip()
    if not s:
        return False
    # Year numbers like 2020, 2021, etc.
    if len(s) == 4 and s.isdigit() and 1990 <= int(s) <= 2100:
        return True
    # Period labels like Q1, H1-2025, FY2024, etc.
    s_lower = s.lower()
    if any(s_lower.startswith(p) for p in ("q1", "q2", "q3", "q4", "h1", "h2", "fy", "ytd")):
        return True
    return False


def _find_header_row(rows_values: list[tuple]) -> int:
    """Find the row index (0-based) that contains column headers.

    The header row is the first row where at least 2 cells look like
    headers (dates, years, period labels).  Falls back to 0 if nothing
    is found in the first 15 rows.
    """
    for i, row in enumerate(rows_values[:15]):
        header_count = sum(1 for v in row if _is_header_value(v))
        if header_count >= 2:
            return i
    return 0


def _find_label_column(rows_values: list[tuple], header_row: int) -> int:
    """Find the column index (0-based) that contains row labels.

    The label column is the first column where most data rows (below
    the header) contain non-empty, non-numeric strings.  Falls back
    to 0.
    """
    if not rows_values:
        return 0

    max_cols = max(len(r) for r in rows_values[:30])
    # Only check the first few columns
    check_cols = min(max_cols, 4)
    data_rows = rows_values[header_row + 1: header_row + 30]

    if not data_rows:
        return 0

    for col_idx in range(check_cols):
        label_count = 0
        total = 0
        for row in data_rows:
            if col_idx >= len(row):
                continue
            v = row[col_idx]
            if v is None:
                continue
            total += 1
            if isinstance(v, str) and v.strip() and not _is_numeric(v):
                label_count += 1
        # If this column has string labels in more than 40% of non-empty rows
        if total > 0 and label_count / total > 0.4:
            return col_idx

    return 0


class DocumentParser:
    def parse_excel(self, file_path: Path) -> list[RawExtraction]:
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
        extractions = []

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]

            if not _is_financial_sheet(sheet_name):
                rows = list(ws.iter_rows(max_row=15, values_only=False))
                has_financial = False
                for row in rows:
                    for cell in row:
                        if cell.value and isinstance(cell.value, str):
                            if any(kw in cell.value.lower() for kw in FINANCIAL_KEYWORDS):
                                has_financial = True
                                break
                    if has_financial:
                        break
                if not has_financial:
                    continue

            rows_list = list(ws.iter_rows(values_only=False))

            if not rows_list:
                continue

            # Convert to values for detection logic
            rows_values = [tuple(c.value for c in row) for row in rows_list]

            # Auto-detect header row and label column
            header_row_idx = _find_header_row(rows_values)
            label_col_idx = _find_label_column(rows_values, header_row_idx)

            # Build headers dict from the detected header row
            headers: dict[int, str] = {}
            for cell in rows_list[header_row_idx]:
                if cell.value is not None:
                    headers[cell.column] = str(cell.value)

            # Extract data from rows below the header
            for row in rows_list[header_row_idx + 1:]:
                if label_col_idx >= len(row):
                    continue
                label_cell = row[label_col_idx]
                if label_cell is None or label_cell.value is None:
                    continue

                raw_label = str(label_cell.value).strip()
                if not raw_label:
                    continue

                for cell in row[label_col_idx + 1:]:
                    if _is_numeric(cell.value):
                        extractions.append(
                            RawExtraction(
                                raw_label=raw_label,
                                raw_value=_to_numeric(cell.value),
                                sheet=sheet_name,
                                cell=_cell_ref(cell.row, cell.column),
                                column_header=headers.get(cell.column),
                                row_index=cell.row,
                            )
                        )

        wb.close()
        return extractions
