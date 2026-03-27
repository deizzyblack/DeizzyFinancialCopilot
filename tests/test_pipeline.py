from pathlib import Path

import openpyxl

from src.api.pipeline import Pipeline


def _create_test_excel(path: Path) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Income Statement"

    ws["A1"] = "Metric"
    ws["B1"] = "Q2 2025"
    ws["C1"] = "Q1 2025"

    ws["A2"] = "Revenue"
    ws["B2"] = 1200000
    ws["C2"] = 1100000

    ws["A3"] = "EBITDA"
    ws["B3"] = 300000
    ws["C3"] = 280000

    ws["A4"] = "Net Income"
    ws["B4"] = 150000
    ws["C4"] = 140000

    ws2 = wb.create_sheet("Balance Sheet")
    ws2["A1"] = "Item"
    ws2["B1"] = "Q2 2025"

    ws2["A2"] = "Total Assets"
    ws2["B2"] = 5000000

    ws2["A3"] = "Total Liabilities"
    ws2["B3"] = 3000000

    ws2["A4"] = "Total Equity"
    ws2["B4"] = 2000000

    file_path = path / "test_financials.xlsx"
    wb.save(file_path)
    return file_path


class TestPipeline:
    def test_full_pipeline(self, db_session, tmp_path):
        excel_file = _create_test_excel(tmp_path)
        pipeline = Pipeline(db_session, upload_dir=str(tmp_path / "uploads"))

        result = pipeline.process_file(
            file_path=excel_file,
            company_id="ACME",
            uploaded_by="test_user",
        )

        assert result.status == "COMPLETED"
        assert result.records_extracted > 0
        assert result.records_created > 0
        assert len(result.actions) > 0

    def test_duplicate_detection(self, db_session, tmp_path):
        excel_file = _create_test_excel(tmp_path)
        pipeline = Pipeline(db_session, upload_dir=str(tmp_path / "uploads"))

        result1 = pipeline.process_file(excel_file, company_id="ACME")
        result2 = pipeline.process_file(excel_file, company_id="ACME")

        assert result1.status == "COMPLETED"
        assert result2.status == "DUPLICATE"

    def test_pipeline_audit_trail(self, db_session, tmp_path):
        excel_file = _create_test_excel(tmp_path)
        pipeline = Pipeline(db_session, upload_dir=str(tmp_path / "uploads"))

        pipeline.process_file(excel_file, company_id="ACME")

        audit_log = pipeline.audit.get_full_log()
        assert len(audit_log) > 0

        event_types = [e.event_type for e in audit_log]
        assert "FILE_INGESTED" in event_types
        assert "DATA_PARSED" in event_types

    def test_version_increments(self, db_session, tmp_path):
        """Verify version increments when same metric/period is stored again."""
        excel_file = _create_test_excel(tmp_path)
        pipeline = Pipeline(db_session, upload_dir=str(tmp_path / "uploads"))

        pipeline.process_file(excel_file, company_id="ACME")

        records = pipeline.storage.get_records_for_period("ACME", "Q2-2025")
        metrics_seen = {}
        for r in records:
            key = r.record.metric.value
            if key not in metrics_seen:
                metrics_seen[key] = r.version
            else:
                metrics_seen[key] = max(metrics_seen[key], r.version)

        # First file, first version for each metric
        for v in metrics_seen.values():
            assert v == 1

        # Ingest a second file with same data but different content
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Income Statement"
        ws["A1"] = "Metric"
        ws["B1"] = "Q2 2025"
        ws["A2"] = "Revenue"
        ws["B2"] = 1300000  # different value
        file2 = tmp_path / "test_financials_v2.xlsx"
        wb.save(file2)

        pipeline2 = Pipeline(db_session, upload_dir=str(tmp_path / "uploads"))
        pipeline2.process_file(file2, company_id="ACME")

        records2 = pipeline2.storage.get_records_for_period("ACME", "Q2-2025")
        revenue_versions = [
            r.version for r in records2 if r.record.metric.value == "Revenue"
        ]
        assert max(revenue_versions) == 2

    def test_records_persisted_to_db(self, db_session, tmp_path):
        """Verify financial records are in the DB after pipeline run."""
        from src.models.database import FinancialRecord

        excel_file = _create_test_excel(tmp_path)
        pipeline = Pipeline(db_session, upload_dir=str(tmp_path / "uploads"))
        pipeline.process_file(excel_file, company_id="ACME")

        count = db_session.query(FinancialRecord).count()
        assert count > 0

    def test_audit_persisted_to_db(self, db_session, tmp_path):
        """Verify audit log entries are in the DB after pipeline run."""
        from src.models.database import AuditLog

        excel_file = _create_test_excel(tmp_path)
        pipeline = Pipeline(db_session, upload_dir=str(tmp_path / "uploads"))
        pipeline.process_file(excel_file, company_id="ACME")

        count = db_session.query(AuditLog).count()
        assert count > 0
