from pathlib import Path

from src.core.enums import FileStatus
from src.ingestion.service import IngestionService


class TestIngestionService:
    def test_ingest_new_file(self, db_session, tmp_path):
        svc = IngestionService(db_session, upload_dir=str(tmp_path / "uploads"))
        test_file = tmp_path / "test.xlsx"
        test_file.write_bytes(b"fake excel content")

        result = svc.ingest_file(test_file)

        assert result.status == FileStatus.NEW
        assert result.filename == "test.xlsx"
        assert result.file_hash
        assert result.size_bytes > 0

    def test_ingest_duplicate_file(self, db_session, tmp_path):
        svc = IngestionService(db_session, upload_dir=str(tmp_path / "uploads"))
        test_file = tmp_path / "test.xlsx"
        test_file.write_bytes(b"fake excel content")

        result1 = svc.ingest_file(test_file)
        result2 = svc.ingest_file(test_file)

        assert result1.status == FileStatus.NEW
        assert result2.status == FileStatus.DUPLICATE

    def test_ingest_different_files(self, db_session, tmp_path):
        svc = IngestionService(db_session, upload_dir=str(tmp_path / "uploads"))
        file1 = tmp_path / "file1.xlsx"
        file1.write_bytes(b"content 1")
        file2 = tmp_path / "file2.xlsx"
        file2.write_bytes(b"content 2")

        result1 = svc.ingest_file(file1)
        result2 = svc.ingest_file(file2)

        assert result1.status == FileStatus.NEW
        assert result2.status == FileStatus.NEW
        assert result1.file_hash != result2.file_hash

    def test_file_not_found(self, db_session, tmp_path):
        svc = IngestionService(db_session, upload_dir=str(tmp_path / "uploads"))
        try:
            svc.ingest_file(Path("/nonexistent/file.xlsx"))
            assert False, "Should have raised"
        except FileNotFoundError:
            pass

    def test_hash_deterministic(self, db_session, tmp_path):
        svc = IngestionService(db_session, upload_dir=str(tmp_path / "uploads"))
        test_file = tmp_path / "test.xlsx"
        test_file.write_bytes(b"consistent content")

        hash1 = svc.compute_hash(test_file)
        hash2 = svc.compute_hash(test_file)
        assert hash1 == hash2

    def test_file_persisted_to_db(self, db_session, tmp_path):
        """Verify file metadata is actually written to the database."""
        from src.models.database import FileRecord

        svc = IngestionService(db_session, upload_dir=str(tmp_path / "uploads"))
        test_file = tmp_path / "test.xlsx"
        test_file.write_bytes(b"persisted content")

        result = svc.ingest_file(test_file)
        db_session.flush()

        row = db_session.query(FileRecord).filter(FileRecord.id == str(result.file_id)).first()
        assert row is not None
        assert row.status == "NEW"
        assert row.filename == "test.xlsx"
