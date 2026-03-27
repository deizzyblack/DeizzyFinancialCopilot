export interface RecordOutcome {
  record_id: string;
  metric: string | null;
  value: number;
  period: string;
  confidence: number;
  decision: string;
  reason: string;
}

export interface PipelineResult {
  file_id: string;
  filename: string;
  status: string;
  records_extracted: number;
  records_created: number;
  outcomes: RecordOutcome[];
  errors: string[];
}

export interface PendingRecord {
  record_id: string;
  company_id: string;
  metric: string | null;
  value: number;
  normalized_period: string;
  confidence: number;
  decision: string;
  reason: string;
  source_file: string;
  status: string;
  version: number;
  created_at: string;
}

export interface PaginatedRecords {
  records: PendingRecord[];
  total: number;
  page: number;
  per_page: number;
}

export interface ConfidenceBreakdown {
  extraction: number;
  mapping: number;
  sanity: number;
  source: number;
  historical: number;
}

export interface RecordDetail {
  record_id: string;
  company_id: string;
  status: string;
  version: number;
  metric: string;
  value: number;
  normalized_period: string;
  source_file: string;
  sheet_name: string;
  cell_reference: string;
  raw_label: string;
  mapped_metric: string;
  mapping_method: string;
  mapping_reason: string;
  raw_period: string;
  period_type: string;
  confidence_total: number;
  confidence_breakdown: ConfidenceBreakdown;
  sanity_passed: boolean;
  sanity_issues: string[];
  change_type: string;
  previous_value: number | null;
  delta: number | null;
  delta_percent: number | null;
  decision: string;
  decision_reason: string;
  created_at: string;
}

export interface ExecuteResult {
  record_id: string;
  action: string;
  new_status: string;
  success: boolean;
}

export interface AuditEntry {
  id: string;
  event_type: string;
  timestamp: string;
  file_id: string | null;
  record_id: string | null;
  details: Record<string, unknown>;
}

export interface PaginatedAudit {
  entries: AuditEntry[];
  total: number;
  page: number;
  per_page: number;
}
