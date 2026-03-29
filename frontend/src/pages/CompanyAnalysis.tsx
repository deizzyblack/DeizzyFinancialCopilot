import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getCompanyAnalysis } from "../api";
import type {
  AggregatedAnomaly,
  AnalysisAnomaly,
  CompanyAnalysis as CompanyAnalysisType,
  MetricComparison,
  MissingItem,
  TrustAssessment,
} from "../types";

const AGGREGATION_THRESHOLD = 20;

function formatNumber(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + "B";
  if (abs >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (abs >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toFixed(0);
}

function severityClass(s: string): string {
  if (s === "critical") return "severity-critical";
  if (s === "warning") return "severity-warning";
  return "severity-normal";
}

function kindLabel(kind: string): string {
  if (kind === "sanity_failure") return "Sanity";
  if (kind === "hard_block") return "Blocked";
  if (kind === "weak_mapping") return "Mapping";
  return kind;
}

function missingTypeLabel(type: string): string {
  if (type === "absent_in_latest") return "Missing";
  if (type === "failed_mapping") return "Unmapped";
  if (type === "filtered_noise") return "Filtered";
  if (type === "partial_balance_sheet") return "Partial BS";
  if (type === "period_regression") return "Regression";
  return type;
}

function trustLabelClass(label: string): string {
  if (label === "high") return "trust-high";
  if (label === "medium") return "trust-medium";
  return "trust-low";
}

/* ── Header: executive summary strip ── */
function AnalysisHeader({ data }: { data: CompanyAnalysisType }) {
  const warnClass = data.comparison_warnings > 0 ? "summary-stat-warn" : "summary-stat-muted";
  const anomClass = data.anomaly_count > 0 ? "summary-stat-crit" : "summary-stat-muted";
  const missClass = data.missing_count > 0 ? "summary-stat-warn" : "summary-stat-muted";

  return (
    <header className="analysis-header">
      <div className="analysis-header-top">
        <span className="analysis-company">{data.company_id}</span>
        <div className="analysis-summary-strip">
          <span className="summary-period">{data.latest_period}</span>
          {data.previous_period && (
            <>
              <span className="summary-vs">vs</span>
              <span className="summary-period">{data.previous_period}</span>
            </>
          )}
          <span className="summary-sep">|</span>
          <span className={warnClass}>{data.comparison_warnings} warnings</span>
          <span className="summary-sep">/</span>
          <span className={anomClass}>{data.anomaly_count} anomalies</span>
          <span className="summary-sep">/</span>
          <span className={missClass}>{data.missing_count} missing</span>
          <span className="summary-sep">|</span>
          <span className={`summary-trust-label ${trustLabelClass(data.trust.label)}`}>
            {data.trust.label} trust
          </span>
        </div>
      </div>
    </header>
  );
}

/* ── Trust ── */
function TrustSection({ trust }: { trust: TrustAssessment }) {
  const pct = Math.round(trust.overall_score * 100);
  const barClass = "trust-bar-" + trust.label;

  return (
    <section className="analysis-section">
      <h2 className="section-title">Data Trust</h2>
      <div className="trust-bar-container">
        <div className="trust-bar-track">
          <div className={`trust-bar-fill ${barClass}`} style={{ width: `${pct}%` }} />
        </div>
        <span className="trust-bar-label">
          {pct}% &mdash; <span className={`trust-label-${trust.label}`}>{trust.label}</span>
        </span>
      </div>
      <div className="trust-kv-row">
        <div className="trust-kv">
          <span className="trust-kv-num trust-kv-green">{trust.approved_count}</span>
          <span className="trust-kv-label">approved</span>
        </div>
        <div className="trust-kv">
          <span className="trust-kv-num trust-kv-muted">{trust.pending_count}</span>
          <span className="trust-kv-label">pending</span>
        </div>
        <div className="trust-kv">
          <span className="trust-kv-num trust-kv-red">{trust.rejected_count}</span>
          <span className="trust-kv-label">rejected</span>
        </div>
        <div className="trust-kv">
          <span className="trust-kv-num trust-kv-amber">{trust.flagged_count}</span>
          <span className="trust-kv-label">flagged</span>
        </div>
      </div>
      <div className="trust-details">
        <div className="trust-detail-row">
          <span>Low confidence records</span>
          <span className={trust.low_confidence_count > 0 ? "text-amber" : ""}>
            {trust.low_confidence_count}
          </span>
        </div>
        <div className="trust-detail-row">
          <span>Sanity failures</span>
          <span className={trust.sanity_failures > 0 ? "text-red" : ""}>
            {trust.sanity_failures}
          </span>
        </div>
        <div className="trust-detail-row">
          <span>Hard blocked</span>
          <span className={trust.hard_blocked_count > 0 ? "text-red" : ""}>
            {trust.hard_blocked_count}
          </span>
        </div>
        <div className="trust-detail-row">
          <span>Weakest area</span>
          <span className="text-muted">
            {trust.weakest_area} @ {(trust.weakest_score * 100).toFixed(0)}%
          </span>
        </div>
      </div>
    </section>
  );
}

/* ── Comparisons ── */
function ComparisonsSection({
  comparisons,
  hasPrevious,
  periodTypeMismatch,
}: {
  comparisons: MetricComparison[];
  hasPrevious: boolean;
  periodTypeMismatch: boolean;
}) {
  if (comparisons.length === 0) {
    return (
      <section className="analysis-section">
        <h2 className="section-title">Changes</h2>
        <div className="empty-state">No mapped metrics found</div>
      </section>
    );
  }

  const isRevision = comparisons.some(
    (c) => c.comparison_warning?.includes("revisions within the same period"),
  );

  return (
    <section className="analysis-section">
      <h2 className="section-title">Changes</h2>
      {!hasPrevious && !isRevision && (
        <div className="info-banner">Single period &mdash; no comparison available</div>
      )}
      {isRevision && (
        <div className="info-banner">Revision comparison &mdash; old vs revised values</div>
      )}
      {periodTypeMismatch && comparisons[0]?.comparison_warning && (
        <div className="info-banner info-banner-warning">
          {comparisons[0].comparison_warning}
        </div>
      )}
      <div className="comparison-table-wrap">
        <table className="comparison-table">
          <thead>
            <tr>
              <th>Metric</th>
              {(hasPrevious || isRevision) && (
                <th className="num-col">{isRevision ? "Before" : "Previous"}</th>
              )}
              <th className="num-col">{isRevision ? "Revised" : "Current"}</th>
              {(hasPrevious || isRevision) && <th className="num-col">Delta</th>}
              {(hasPrevious || isRevision) && <th className="num-col">%</th>}
              {(hasPrevious || isRevision) && <th>Status</th>}
            </tr>
          </thead>
          <tbody>
            {comparisons.map((c) => (
              <tr key={c.metric} className={severityClass(c.severity)}>
                <td className="metric-name">{c.metric}</td>
                {(hasPrevious || isRevision) && (
                  <td className="num-col">
                    {c.previous_value !== null ? formatNumber(c.previous_value) : "\u2014"}
                  </td>
                )}
                <td className="num-col">{formatNumber(c.current_value)}</td>
                {(hasPrevious || isRevision) && (
                  <td className="num-col">
                    {c.delta !== null ? formatNumber(c.delta) : "\u2014"}
                  </td>
                )}
                {(hasPrevious || isRevision) && (
                  <td className="num-col">
                    {c.delta_percent !== null
                      ? `${c.delta_percent > 0 ? "+" : ""}${c.delta_percent.toFixed(1)}%`
                      : "\u2014"}
                  </td>
                )}
                {(hasPrevious || isRevision) && (
                  <td>
                    <span className={`pill pill-${c.severity}`}>
                      {c.severity === "normal" ? "ok" : c.severity}
                    </span>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {comparisons.some((c) => c.explanation) && (
        <div className="comparison-explanations">
          {comparisons
            .filter((c) => c.explanation)
            .map((c) => (
              <div key={c.metric} className={`explanation-row ${severityClass(c.severity)}`}>
                <span className="explanation-metric">{c.metric}:</span> {c.explanation}
              </div>
            ))}
        </div>
      )}
    </section>
  );
}

/* ── Anomalies ── */
function AggregatedAnomaliesView({ aggregated }: { aggregated: AggregatedAnomaly[] }) {
  return (
    <div className="anomaly-list">
      {aggregated.map((a, i) => (
        <div key={i} className={`anomaly-card ${severityClass(a.severity)}`}>
          <div className="anomaly-header">
            <span className={`pill pill-${a.severity}`}>{a.severity}</span>
            <span className="pill pill-kind">{kindLabel(a.kind)}</span>
            <span className="anomaly-count-badge">{a.count}x</span>
          </div>
          <p className="anomaly-issue">{a.issue}</p>
          <div className="anomaly-meta">
            <span>Metrics: {a.metrics.join(", ")}</span>
            <span>
              Periods:{" "}
              {a.periods.length > 3
                ? `${a.periods.slice(0, 3).join(", ")} +${a.periods.length - 3}`
                : a.periods.join(", ")}
            </span>
          </div>
          {a.sample_record_ids.length > 0 && (
            <div className="anomaly-samples">
              {a.sample_record_ids.map((id) => (
                <Link key={id} to={`/records/${id}`} className="anomaly-link">
                  {id.slice(0, 8)}
                </Link>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function DetailedAnomaliesView({ anomalies }: { anomalies: AnalysisAnomaly[] }) {
  return (
    <div className="anomaly-list">
      {anomalies.map((a, i) => (
        <div key={i} className={`anomaly-card ${severityClass(a.severity)}`}>
          <div className="anomaly-header">
            <span className={`pill pill-${a.severity}`}>{a.severity}</span>
            <span className="pill pill-kind">{kindLabel(a.kind)}</span>
            <span className="anomaly-metric">{a.metric} &mdash; {a.period}</span>
          </div>
          <div className="anomaly-body">
            <span className="anomaly-value">Value: {formatNumber(a.value)}</span>
            <p className="anomaly-issue">{a.issue}</p>
          </div>
          <Link to={`/records/${a.record_id}`} className="anomaly-link">
            View record
          </Link>
        </div>
      ))}
    </div>
  );
}

function AnomaliesSection({
  anomalies,
  aggregated,
}: {
  anomalies: AnalysisAnomaly[];
  aggregated: AggregatedAnomaly[];
}) {
  const [showDetailed, setShowDetailed] = useState(false);
  const isLarge = anomalies.length > AGGREGATION_THRESHOLD;

  if (anomalies.length === 0) {
    return (
      <section className="analysis-section">
        <h2 className="section-title">Anomalies</h2>
        <div className="empty-state-ok">No anomalies detected</div>
      </section>
    );
  }

  return (
    <section className="analysis-section">
      <div className="section-title-row">
        <h2 className="section-title">
          Anomalies <span className="section-count">{anomalies.length}</span>
        </h2>
        {isLarge && (
          <button className="toggle-view-btn" onClick={() => setShowDetailed(!showDetailed)}>
            {showDetailed ? "Grouped" : "All"}
          </button>
        )}
      </div>
      {isLarge && !showDetailed ? (
        <AggregatedAnomaliesView aggregated={aggregated} />
      ) : (
        <DetailedAnomaliesView anomalies={anomalies} />
      )}
    </section>
  );
}

/* ── Missing ── */
function MissingSection({ missing }: { missing: MissingItem[] }) {
  if (missing.length === 0) {
    return (
      <section className="analysis-section">
        <h2 className="section-title">Missing Metrics</h2>
        <div className="empty-state-ok">All expected metrics present</div>
      </section>
    );
  }

  return (
    <section className="analysis-section">
      <h2 className="section-title">Missing Metrics</h2>
      <div className="missing-list">
        {missing.map((m, i) => (
          <div key={i} className="missing-card">
            <div className="missing-header">
              <span className="pill pill-missing-type">{missingTypeLabel(m.type)}</span>
              <span className="missing-metric">{m.metric}</span>
              <span className="missing-period">{m.period}</span>
            </div>
            <p className="missing-reason">{m.reason}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ── Page ── */
export function CompanyAnalysis() {
  const [searchParams, setSearchParams] = useSearchParams();
  const companyId = searchParams.get("id") || "";
  const [inputValue, setInputValue] = useState(companyId);
  const [data, setData] = useState<CompanyAnalysisType | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) return;
    setLoading(true);
    setError(null);
    getCompanyAnalysis(companyId)
      .then(setData)
      .catch((e) => {
        setData(null);
        setError(e.message || "Failed to load analysis");
      })
      .finally(() => setLoading(false));
  }, [companyId]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = inputValue.trim();
    if (trimmed) setSearchParams({ id: trimmed });
  }

  return (
    <div className="analysis-page">
      <form className="analysis-search" onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Enter company ID..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          className="analysis-input"
        />
        <button type="submit" className="btn-primary">Analyze</button>
      </form>

      {loading && (
        <div className="analysis-loading">
          <div className="spinner" />
          <span>Analyzing {companyId}...</span>
        </div>
      )}

      {error && (
        <div className="analysis-error">
          <h2>No data found</h2>
          <p>
            No financial data for &quot;{companyId}&quot;.{" "}
            <Link to="/upload">Upload a file</Link> to begin.
          </p>
        </div>
      )}

      {data && !loading && (
        <>
          <AnalysisHeader data={data} />
          <TrustSection trust={data.trust} />
          <ComparisonsSection
            comparisons={data.comparisons}
            hasPrevious={data.previous_period !== null}
            periodTypeMismatch={data.period_type_mismatch}
          />
          <AnomaliesSection
            anomalies={data.anomalies}
            aggregated={data.aggregated_anomalies}
          />
          <MissingSection missing={data.missing} />

          <section className="analysis-section">
            <h2 className="section-title">History</h2>
            <span className="text-muted" style={{ fontSize: 12 }}>
              {data.upload_count} file{data.upload_count !== 1 ? "s" : ""} uploaded
              across {data.periods_available.length} period
              {data.periods_available.length !== 1 ? "s" : ""}
            </span>
          </section>
        </>
      )}

      {!companyId && !loading && !error && (
        <div className="analysis-empty">
          <h2>Company Analysis</h2>
          <p>
            Enter a company ID to review changes, anomalies, missing data, and trust assessment.
          </p>
        </div>
      )}
    </div>
  );
}
