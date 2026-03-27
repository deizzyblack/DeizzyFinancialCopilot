import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.core.config import settings


class Base(DeclarativeBase):
    pass


class FileRecord(Base):
    __tablename__ = "files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_hash = Column(String(64), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(100))
    uploaded_by = Column(String(200), default="system")
    uploaded_at = Column(DateTime, default=lambda: datetime.now(UTC))
    status = Column(String(20), nullable=False, default="NEW")


class FinancialRecord(Base):
    __tablename__ = "financial_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(100), nullable=False, index=True)
    metric = Column(String(50), nullable=False, index=True)
    value = Column(Float, nullable=False)
    raw_label = Column(String(500))
    period = Column(String(20), nullable=False, index=True)
    period_type = Column(String(20), nullable=False)
    file_id = Column(String(36), nullable=False)
    sheet = Column(String(200))
    cell = Column(String(20))
    status = Column(String(20), nullable=False, default="PENDING")
    mapping_score = Column(Float, default=0.0)
    period_confidence = Column(Float, default=0.0)
    confidence_total = Column(Float, default=0.0)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class MappingMemory(Base):
    __tablename__ = "mapping_memory"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(100), nullable=False, index=True)
    original_label = Column(String(500), nullable=False)
    mapped_metric = Column(String(50), nullable=False)
    approved = Column(String(5), default="false")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(50), nullable=False, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))
    file_id = Column(String(36), nullable=True)
    record_id = Column(String(36), nullable=True)
    actor = Column(String(200), default="system")
    details_json = Column(Text, default="{}")

    @property
    def details(self) -> dict:
        try:
            return json.loads(self.details_json or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

    @details.setter
    def details(self, value: dict):
        self.details_json = json.dumps(value, default=str)


def get_engine(url: str | None = None):
    return create_engine(url or settings.database_url)


def get_session_factory(url: str | None = None):
    engine = get_engine(url)
    return sessionmaker(bind=engine)


def create_tables(engine):
    Base.metadata.create_all(engine)
