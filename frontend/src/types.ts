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

export interface CompanyBenchmark {
  company_id: string;
  record_count: number;
  metrics: string[];
  records: Array<{
    metric: string;
    value: number;
    period: string;
    version: number;
    confidence: number;
  }>;
}

export interface BenchmarkingResult {
  companies: CompanyBenchmark[];
  total_companies: number;
  filters: { metric: string | null; period: string | null };
}

export interface PaginatedAudit {
  entries: AuditEntry[];
  total: number;
  page: number;
  per_page: number;
}

// Company Analysis types
export interface MetricComparison {
  metric: string;
  current_value: number;
  current_period: string;
  previous_value: number | null;
  previous_period: string | null;
  delta: number | null;
  delta_percent: number | null;
  severity: "normal" | "warning" | "critical";
  explanation: string;
}

export interface AnalysisAnomaly {
  metric: string;
  period: string;
  value: number;
  issue: string;
  kind: "sanity_failure" | "hard_block" | "weak_mapping";
  severity: "warning" | "critical";
  record_id: string;
}

export interface MissingItem {
  metric: string;
  period: string;
  reason: string;
  type: "absent_in_latest" | "partial_balance_sheet" | "period_regression";
}

export interface TrustAssessment {
  overall_score: number;
  label: "high" | "medium" | "low";
  total_records: number;
  approved_count: number;
  pending_count: number;
  rejected_count: number;
  flagged_count: number;
  low_confidence_count: number;
  sanity_failures: number;
  hard_blocked_count: number;
  weakest_area: string;
  weakest_score: number;
}

export interface CompanyAnalysis {
  company_id: string;
  periods_available: string[];
  latest_period: string | null;
  previous_period: string | null;
  upload_count: number;
  comparisons: MetricComparison[];
  anomalies: AnalysisAnomaly[];
  missing: MissingItem[];
  trust: TrustAssessment;
  comparison_warnings: number;
  anomaly_count: number;
  missing_count: number;
}
