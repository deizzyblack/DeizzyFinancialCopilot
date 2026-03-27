"""Tests for parser auto-detection of label columns, header rows, and sheet names."""

from pathlib import Path

import openpyxl
import pytest

from src.parser.service import DocumentParser, _find_header_row, _find_label_column


@pytest.fixture
def parser():
    return DocumentParser()


def _write_xlsx(path: Path, sheets: dict) -> Path:
    """Helper: create an xlsx with {sheet_name: [[row1], [row2], ...]}."""
    wb = openpyxl.Workbook()
    first = True
    for name, rows in sheets.items():
        ws = wb.active if first else wb.create_sheet(name)
        if first:
            ws.title = name
            first = False
        for row in rows:
            ws.append(row)
    wb.save(path)
    wb.close()
    return path


class TestLabelColumnDetection:
    def test_label_in_col_a(self, parser, tmp_path):
        """Standard layout: labels in column A."""
        path = _write_xlsx(
            tmp_path / "col_a.xlsx",
            {
                "Income Statement": [
                    ["Metric", "Q1-2025"],
                    ["Revenue", 5000000],
                    ["EBITDA", 1200000],
                ]
            },
        )
        results = parser.parse_excel(path)
        labels = {r.raw_label for r in results}
        assert "Revenue" in labels
        assert "EBITDA" in labels

    def test_label_in_col_b(self, parser, tmp_path):
        """Labels in column B, column A is empty spacer."""
        path = _write_xlsx(
            tmp_path / "col_b.xlsx",
            {
                "Income Statement": [
                    [None, "Metric", "Q1-2025", "Q2-2025"],
                    [None, "Revenue", 5000000, 5500000],
                    [None, "EBITDA", 1200000, 1350000],
                    [None, "Net Income", 800000, 900000],
                ]
            },
        )
        results = parser.parse_excel(path)
        labels = {r.raw_label for r in results}
        assert "Revenue" in labels
        assert "EBITDA" in labels
        assert "Net Income" in labels
        assert len(results) == 6  # 3 labels * 2 periods

    def test_label_col_detection_logic(self):
        """Unit test for _find_label_column."""
        rows = [
            (None, "Metric", "2024", "2025"),
            (None, "Revenue", 100, 200),
            (None, "EBITDA", 50, 60),
            (None, "Cash", 30, 40),
        ]
        assert _find_label_column(rows, 0) == 1


class TestHeaderRowDetection:
    def test_header_in_row_1(self, parser, tmp_path):
        """Standard layout: headers in row 1."""
        path = _write_xlsx(
            tmp_path / "row1.xlsx",
            {
                "Income Statement": [
                    ["Metric", "Q1-2025"],
                    ["Revenue", 5000000],
                ]
            },
        )
        results = parser.parse_excel(path)
        assert len(results) == 1
        assert results[0].column_header == "Q1-2025"

    def test_header_in_later_row(self, parser, tmp_path):
        """Headers start on row 4, rows 1-3 are title/spacer."""
        path = _write_xlsx(
            tmp_path / "row4.xlsx",
            {
                "Financial Statement": [
                    [None],
                    ["Company XYZ"],
                    [None],
                    ["($ in USD)", "2023", "2024", "2025"],
                    ["Revenue", 3000000, 4000000, 5000000],
                    ["Cash", 2000000, 2500000, 3000000],
                ]
            },
        )
        results = parser.parse_excel(path)
        assert len(results) == 6  # 2 labels * 3 years
        headers = {r.column_header for r in results}
        assert "2023" in headers
        assert "2024" in headers
        assert "2025" in headers

    def test_header_row_detection_logic(self):
        """Unit test for _find_header_row."""
        rows = [
            (None, None, None),
            ("Title", None, None),
            (None, None, None),
            ("Item", "2023", "2024"),
            ("Revenue", 100, 200),
        ]
        assert _find_header_row(rows) == 3


class TestPnlSheetDetection:
    def test_pnl_sheet_detected(self, parser, tmp_path):
        """Sheet named 'P&L' should be detected as financial."""
        path = _write_xlsx(
            tmp_path / "pnl.xlsx",
            {
                "P&L": [
                    ["Item", "FY-2025"],
                    ["Revenue", 10000000],
                    ["Net Income", 2000000],
                ]
            },
        )
        results = parser.parse_excel(path)
        labels = {r.raw_label for r in results}
        assert "Revenue" in labels
        assert "Net Income" in labels

    def test_content_scan_extended_rows(self, parser, tmp_path):
        """Financial keywords in rows 6-15 should still be detected."""
        rows = [[None]] * 10  # 10 empty rows
        rows.append(["Revenue", 5000000])  # row 11
        rows.append(["EBITDA", 1200000])   # row 12
        # Need a header row with period-like values for detection
        rows[0] = ["Metric", "Q1-2025"]
        path = _write_xlsx(tmp_path / "late_content.xlsx", {"Data": rows})
        results = parser.parse_excel(path)
        labels = {r.raw_label for r in results}
        assert "Revenue" in labels


class TestRealFileCompatibility:
    def test_demo_file_clean(self, parser):
        """Existing demo file still produces correct output."""
        path = Path("sample_data/acme_q3_2025_clean.xlsx")
        if not path.exists():
            pytest.skip("Demo file not available")
        results = parser.parse_excel(path)
        assert len(results) == 6
        labels = {r.raw_label for r in results}
        assert "Revenue" in labels
        assert "EBITDA" in labels
        assert all(r.column_header == "Q3-2025" for r in results)

    def test_demo_file_messy(self, parser):
        """Messy demo file still produces correct output."""
        path = Path("sample_data/beta_q3_2025_messy.xlsx")
        if not path.exists():
            pytest.skip("Demo file not available")
        results = parser.parse_excel(path)
        assert len(results) == 7
        assert all(r.column_header == "30.09.2025" for r in results)
