import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getCompanyAnalysis } from "../api";
import type {
  AnalysisAnomaly,
  CompanyAnalysis as CompanyAnalysisType,
  MetricComparison,
  MissingItem,
  TrustAssessment,
} from "../types";

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
  if (kind === "sanity_failure") return "Sanity Failure";
  if (kind === "hard_block") return "Hard Block";
  if (kind === "weak_mapping") return "Weak Mapping";
  return kind;
}

function missingTypeLabel(type: string): string {
  if (type === "absent_in_latest") return "Missing";
  if (type === "partial_balance_sheet") return "Partial BS";
  if (type === "period_regression") return "Regression";
  return type;
}

function TrustBar({ score, label }: { score: number; label: string }) {
  const pct = Math.round(score * 100);
  const barClass =
    label === "high"
      ? "trust-bar-high"
      : label === "medium"
        ? "trust-bar-medium"
        : "trust-bar-low";
  return (
    <div className="trust-bar-container">
      <div className="trust-bar-track">
        <div
          className={`trust-bar-fill ${barClass}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="trust-bar-label">
        {pct}% — <span className={`trust-label-${label}`}>{label}</span>
      </span>
    </div>
  );
}

function TrustSection({ trust }: { trust: TrustAssessment }) {
  return (
    <section className="analysis-section">
      <h2 className="section-title">Can I Trust This Data?</h2>
      <TrustBar score={trust.overall_score} label={trust.label} />
      <div className="trust-grid">
        <div className="trust-stat">
          <span className="trust-stat-value trust-approved">
            {trust.approved_count}
          </span>
          <span className="trust-stat-label">Approved</span>
        </div>
        <div className="trust-stat">
          <span className="trust-stat-value trust-pending">
            {trust.pending_count}
          </span>
          <span className="trust-stat-label">Pending</span>
        </div>
        <div className="trust-stat">
          <span className="trust-stat-value trust-rejected">
            {trust.rejected_count}
          </span>
          <span className="trust-stat-label">Rejected</span>
        </div>
        <div className="trust-stat">
          <span className="trust-stat-value trust-flagged">
            {trust.flagged_count}
          </span>
          <span className="trust-stat-label">Flagged</span>
        </div>
      </div>
      <div className="trust-details">
        <div className="trust-detail-row">
          <span>Low confidence records</span>
          <span className={trust.low_confidence_count > 0 ? "text-yellow" : ""}>
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

function ComparisonsSection({
  comparisons,
  hasPrevious,
}: {
  comparisons: MetricComparison[];
  hasPrevious: boolean;
}) {
  if (comparisons.length === 0) {
    return (
      <section className="analysis-section">
        <h2 className="section-title">What Changed?</h2>
        <div className="empty-state">No mapped metrics found</div>
      </section>
    );
  }

  return (
    <section className="analysis-section">
      <h2 className="section-title">What Changed?</h2>
      {!hasPrevious && (
        <div className="info-banner">
          Only one period available — no comparison possible
        </div>
      )}
      <div className="comparison-table-wrap">
        <table className="comparison-table">
          <thead>
            <tr>
              <th>Metric</th>
              {hasPrevious && <th className="num-col">Previous</th>}
              <th className="num-col">Current</th>
              {hasPrevious && <th className="num-col">Delta</th>}
              {hasPrevious && <th className="num-col">%</th>}
              {hasPrevious && <th>Status</th>}
            </tr>
          </thead>
          <tbody>
            {comparisons.map((c) => (
              <tr key={c.metric} className={severityClass(c.severity)}>
                <td className="metric-name">{c.metric}</td>
                {hasPrevious && (
                  <td className="num-col">
                    {c.previous_value !== null
                      ? formatNumber(c.previous_value)
                      : "—"}
                  </td>
                )}
                <td className="num-col">{formatNumber(c.current_value)}</td>
                {hasPrevious && (
                  <td className="num-col">
                    {c.delta !== null ? formatNumber(c.delta) : "—"}
                  </td>
                )}
                {hasPrevious && (
                  <td className="num-col">
                    {c.delta_percent !== null
                      ? `${c.delta_percent > 0 ? "+" : ""}${c.delta_percent.toFixed(1)}%`
                      : "—"}
                  </td>
                )}
                {hasPrevious && (
                  <td>
                    {c.severity === "critical" && (
                      <span className="pill pill-critical">critical</span>
                    )}
                    {c.severity === "warning" && (
                      <span className="pill pill-warning">warning</span>
                    )}
                    {c.severity === "normal" && (
                      <span className="pill pill-normal">ok</span>
                    )}
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
              <div
                key={c.metric}
                className={`explanation-row ${severityClass(c.severity)}`}
              >
                <span className="explanation-metric">{c.metric}:</span>{" "}
                {c.explanation}
              </div>
            ))}
        </div>
      )}
    </section>
  );
}

function AnomaliesSection({ anomalies }: { anomalies: AnalysisAnomaly[] }) {
  if (anomalies.length === 0) {
    return (
      <section className="analysis-section">
        <h2 className="section-title">What Is Wrong?</h2>
        <div className="empty-state empty-state-ok">
          No anomalies detected
        </div>
      </section>
    );
  }

  return (
    <section className="analysis-section">
      <h2 className="section-title">What Is Wrong?</h2>
      <div className="anomaly-list">
        {anomalies.map((a, i) => (
          <div key={i} className={`anomaly-card ${severityClass(a.severity)}`}>
            <div className="anomaly-header">
              <span className={`pill pill-${a.severity}`}>{a.severity}</span>
              <span className="pill pill-kind">{kindLabel(a.kind)}</span>
              <span className="anomaly-metric">
                {a.metric} — {a.period}
              </span>
            </div>
            <div className="anomaly-body">
              <span className="anomaly-value">
                Value: {formatNumber(a.value)}
              </span>
              <p className="anomaly-issue">{a.issue}</p>
            </div>
            <Link
              to={`/records/${a.record_id}`}
              className="anomaly-link"
            >
              View record
            </Link>
          </div>
        ))}
      </div>
    </section>
  );
}

function MissingSection({ missing }: { missing: MissingItem[] }) {
  if (missing.length === 0) {
    return (
      <section className="analysis-section">
        <h2 className="section-title">What Is Missing?</h2>
        <div className="empty-state empty-state-ok">
          All expected metrics present
        </div>
      </section>
    );
  }

  return (
    <section className="analysis-section">
      <h2 className="section-title">What Is Missing?</h2>
      <div className="missing-list">
        {missing.map((m, i) => (
          <div key={i} className="missing-card">
            <div className="missing-header">
              <span className="pill pill-missing-type">
                {missingTypeLabel(m.type)}
              </span>
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
    if (trimmed) {
      setSearchParams({ id: trimmed });
    }
  }

  return (
    <div className="analysis-page">
      {/* Company search */}
      <form className="analysis-search" onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Enter company ID..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          className="analysis-input"
        />
        <button type="submit" className="btn-primary">
          Analyze
        </button>
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
            No financial data found for &quot;{companyId}&quot;.{" "}
            <Link to="/upload">Upload a file</Link> to begin.
          </p>
        </div>
      )}

      {data && !loading && (
        <>
          {/* Header */}
          <header className="analysis-header">
            <div className="analysis-header-title">
              <h1>{data.company_id}</h1>
              <div className="analysis-periods">
                <span className="period-badge period-latest">
                  {data.latest_period}
                </span>
                {data.previous_period && (
                  <>
                    <span className="period-arrow">vs</span>
                    <span className="period-badge period-previous">
                      {data.previous_period}
                    </span>
                  </>
                )}
              </div>
            </div>
            <div className="analysis-header-meta">
              <span>{data.periods_available.length} periods</span>
              <span className="meta-dot" />
              <span>{data.upload_count} uploads</span>
            </div>
            <div className="analysis-header-pills">
              <span
                className={`header-pill ${data.comparison_warnings > 0 ? "pill-warning" : "pill-normal"}`}
              >
                {data.comparison_warnings} warnings
              </span>
              <span
                className={`header-pill ${data.anomaly_count > 0 ? "pill-critical" : "pill-normal"}`}
              >
                {data.anomaly_count} anomalies
              </span>
              <span
                className={`header-pill ${data.missing_count > 0 ? "pill-warning" : "pill-normal"}`}
              >
                {data.missing_count} missing
              </span>
            </div>
          </header>

          {/* Sections */}
          <TrustSection trust={data.trust} />
          <ComparisonsSection
            comparisons={data.comparisons}
            hasPrevious={data.previous_period !== null}
          />
          <AnomaliesSection anomalies={data.anomalies} />
          <MissingSection missing={data.missing} />

          {/* Upload history summary */}
          <section className="analysis-section">
            <h2 className="section-title">Upload History</h2>
            <div className="upload-summary">
              {data.upload_count} file{data.upload_count !== 1 ? "s" : ""}{" "}
              uploaded across {data.periods_available.length} period
              {data.periods_available.length !== 1 ? "s" : ""}
            </div>
          </section>
        </>
      )}

      {!companyId && !loading && !error && (
        <div className="analysis-empty">
          <h2>Company Analysis</h2>
          <p>
            Enter a company ID to see what changed, what is wrong, what is
            missing, and how much you can trust the data.
          </p>
        </div>
      )}
    </div>
  );
}
