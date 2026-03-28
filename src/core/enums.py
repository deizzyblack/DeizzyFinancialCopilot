from enum import Enum


class FileStatus(str, Enum):
    NEW = "NEW"
    DUPLICATE = "DUPLICATE"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RecordStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ChangeType(str, Enum):
    NEW = "NEW"
    DUPLICATE = "DUPLICATE"
    REVISION = "REVISION"


class MappingMethod(str, Enum):
    COMPANY_APPROVED = "company_approved"
    RULE_BASED = "rule_based"
    LLM_FALLBACK = "llm_fallback"


class PeriodType(str, Enum):
    QUARTER = "QUARTER"
    HALF = "HALF"
    YTD = "YTD"
    FULL_YEAR = "FULL_YEAR"
    MONTH = "MONTH"
    UNKNOWN = "UNKNOWN"


class StandardMetric(str, Enum):
    REVENUE = "Revenue"
    EBITDA = "EBITDA"
    GROSS_PROFIT = "Gross Profit"
    NET_INCOME = "Net Income"
    CASH = "Cash"
    ASSETS = "Assets"
    LIABILITIES = "Liabilities"
    EQUITY = "Equity"


class DecisionType(str, Enum):
    AUTO_READY = "AUTO_READY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FLAG = "FLAG"


class ActionType(str, Enum):
    UPDATE = "UPDATE"
    REVIEW = "REVIEW"
    IGNORE = "IGNORE"
    INVESTIGATE = "INVESTIGATE"


class UserAction(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    INVESTIGATE = "INVESTIGATE"


class AuditEventType(str, Enum):
    FILE_INGESTED = "FILE_INGESTED"
    FILE_DUPLICATE = "FILE_DUPLICATE"
    DATA_PARSED = "DATA_PARSED"
    METRIC_MAPPED = "METRIC_MAPPED"
    PERIOD_NORMALIZED = "PERIOD_NORMALIZED"
    RECORD_CREATED = "RECORD_CREATED"
    CHANGE_DETECTED = "CHANGE_DETECTED"
    SANITY_CHECK = "SANITY_CHECK"
    CONFIDENCE_SCORED = "CONFIDENCE_SCORED"
    DECISION_MADE = "DECISION_MADE"
    ACTION_GENERATED = "ACTION_GENERATED"
    USER_ACTION = "USER_ACTION"
    RECORD_APPROVED = "RECORD_APPROVED"
    RECORD_REJECTED = "RECORD_REJECTED"
    PIPELINE_COMPLETE = "PIPELINE_COMPLETE"
