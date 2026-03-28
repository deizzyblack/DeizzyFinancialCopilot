from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from src.core.enums import (
    ActionType,
    ChangeType,
    DecisionType,
    FileStatus,
    MappingMethod,
    PeriodType,
    RecordStatus,
    StandardMetric,
)


class FileMetadata(BaseModel):
    file_id: UUID
    file_hash: str
    filename: str
    size_bytes: int
    mime_type: str
    uploaded_by: str = "system"
    uploaded_at: datetime
    status: FileStatus


class RawExtraction(BaseModel):
    raw_label: str
    raw_value: float | int | str | None
    sheet: str
    cell: str
    column_header: str | None = None
    row_index: int | None = None


class MappingResult(BaseModel):
    metric: StandardMetric | None
    mapping_score: float = Field(ge=0.0, le=1.0)
    method: MappingMethod
    reason: str


class PeriodResult(BaseModel):
    raw_period: str
    normalized_period: str
    period_type: PeriodType
    period_end_date: date | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class CandidateRecord(BaseModel):
    company_id: str
    metric: StandardMetric
    value: float
    raw_label: str
    period: str
    period_type: PeriodType
    file_id: UUID
    sheet: str
    cell: str
    status: RecordStatus = RecordStatus.PENDING
    mapping_score: float = 0.0
    period_confidence: float = 0.0


class ChangeDetectionResult(BaseModel):
    change_type: ChangeType
    old_value: float | None = None
    new_value: float | None = None
    diff: float | None = None
    revision_count: int = 0


class SanityResult(BaseModel):
    passed: bool
    issues: list[str] = []


class ConfidenceScore(BaseModel):
    extraction: float = Field(ge=0.0, le=1.0)
    mapping: float = Field(ge=0.0, le=1.0)
    sanity: float = Field(ge=0.0, le=1.0)
    source: float = Field(ge=0.0, le=1.0)
    historical: float = Field(ge=0.0, le=1.0)
    total: float = Field(ge=0.0, le=1.0)
    hard_blocked: bool = False
    block_reasons: list[str] = []


class DecisionResult(BaseModel):
    decision: DecisionType
    confidence: ConfidenceScore
    reason: str


class ActionRecommendation(BaseModel):
    action: ActionType
    reason: str
    record_id: UUID | None = None
    details: dict[str, Any] = {}


class AuditEntry(BaseModel):
    event_type: str
    timestamp: datetime
    file_id: UUID | None = None
    record_id: UUID | None = None
    actor: str = "system"
    details: dict[str, Any] = {}


class RecordOutcome(BaseModel):
    record_id: UUID
    metric: str | None = None
    value: float = 0.0
    period: str = ""
    confidence: float = 0.0
    decision: str = ""
    reason: str = ""


class PipelineResult(BaseModel):
    file_id: UUID
    filename: str = ""
    status: str
    records_extracted: int = 0
    records_created: int = 0
    unmapped_count: int = 0
    noise_filtered_count: int = 0
    outcomes: list[RecordOutcome] = []
    actions: list[ActionRecommendation] = []
    errors: list[str] = []
