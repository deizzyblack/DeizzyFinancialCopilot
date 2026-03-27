import hashlib
import mimetypes
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.core.config import settings
from src.core.enums import AuditEventType, FileStatus
from src.core.schemas import FileMetadata


class IngestionService:
    def __init__(self, upload_dir: str | None = None):
        self.upload_dir = Path(upload_dir or settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._known_hashes: dict[str, str] = {}

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

        if file_hash in self._known_hashes:
            return FileMetadata(
                file_id=file_id,
                file_hash=file_hash,
                filename=file_path.name,
                size_bytes=file_path.stat().st_size,
                mime_type=mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
                uploaded_by=uploaded_by,
                uploaded_at=datetime.now(timezone.utc),
                status=FileStatus.DUPLICATE,
            )

        dest = self.upload_dir / f"{file_id}_{file_path.name}"
        shutil.copy2(file_path, dest)

        self._known_hashes[file_hash] = str(file_id)

        return FileMetadata(
            file_id=file_id,
            file_hash=file_hash,
            filename=file_path.name,
            size_bytes=file_path.stat().st_size,
            mime_type=mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
            uploaded_by=uploaded_by,
            uploaded_at=datetime.now(timezone.utc),
            status=FileStatus.NEW,
        )

    def get_stored_path(self, file_id: uuid.UUID, filename: str) -> Path:
        return self.upload_dir / f"{file_id}_{filename}"
