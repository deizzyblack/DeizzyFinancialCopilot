import hashlib
import mimetypes
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.enums import FileStatus
from src.core.schemas import FileMetadata
from src.models.database import FileRecord


class IngestionService:
    def __init__(self, session: Session, upload_dir: str | None = None):
        self.session = session
        self.upload_dir = Path(upload_dir or settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def compute_hash(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def ingest_file(
        self,
        file_path: Path,
        uploaded_by: str = "system",
    ) -> FileMetadata:
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        file_hash = self.compute_hash(file_path)
        file_id = uuid.uuid4()
        now = datetime.now(UTC)
        size = file_path.stat().st_size
        mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"

        existing = (
            self.session.query(FileRecord)
            .filter(FileRecord.file_hash == file_hash)
            .first()
        )

        if existing:
            dup_row = FileRecord(
                id=str(file_id),
                file_hash=file_hash,
                filename=file_path.name,
                size_bytes=size,
                mime_type=mime,
                uploaded_by=uploaded_by,
                uploaded_at=now,
                status=FileStatus.DUPLICATE.value,
            )
            self.session.add(dup_row)
            self.session.flush()

            return FileMetadata(
                file_id=file_id,
                file_hash=file_hash,
                filename=file_path.name,
                size_bytes=size,
                mime_type=mime,
                uploaded_by=uploaded_by,
                uploaded_at=now,
                status=FileStatus.DUPLICATE,
            )

        dest = self.upload_dir / f"{file_id}_{file_path.name}"
        shutil.copy2(file_path, dest)

        row = FileRecord(
            id=str(file_id),
            file_hash=file_hash,
            filename=file_path.name,
            size_bytes=size,
            mime_type=mime,
            uploaded_by=uploaded_by,
            uploaded_at=now,
            status=FileStatus.NEW.value,
        )
        self.session.add(row)
        self.session.flush()

        return FileMetadata(
            file_id=file_id,
            file_hash=file_hash,
            filename=file_path.name,
            size_bytes=size,
            mime_type=mime,
            uploaded_by=uploaded_by,
            uploaded_at=now,
            status=FileStatus.NEW,
        )

    def get_stored_path(self, file_id: uuid.UUID, filename: str) -> Path:
        return self.upload_dir / f"{file_id}_{filename}"
