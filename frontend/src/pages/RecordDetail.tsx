import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { executeAction, getRecordDetail } from "../api";
import { ConfidenceBar } from "../components/ConfidenceBar";
import { StatusBadge } from "../components/StatusBadge";
import type { RecordDetail as RecordDetailType } from "../types";

function fmt(n: number): string {
  return n.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

export function RecordDetail() {
  const { id } = useParams<{ id: string }>();
  const [rec, setRec] = useState<RecordDetailType | null>(null);
  const [error, setError] = useState("");
  const [acting, setActing] = useState(false);
  const [actionDone, setActionDone] = useState("");

  useEffect(() => {
    if (!id) return;
    getRecordDetail(id)
      .then(setRec)
      .catch((e) => setError(e.message));
  }, [id]);

  async function handleAction(action: "APPROVE" | "REJECT" | "INVESTIGATE") {
    if (!id) return;
    setActing(true);
    setActionDone("");
    try {
      const res = await executeAction(id, action);
      setActionDone(`${action} - status changed to ${res.new_status}`);
      const updated = await getRecordDetail(id);
      setRec(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setActing(false);
    }
  }

  if (error) return <div className="page"><div className="error-box">{error}</div></div>;
  if (!rec) return (
    <div className="page">
      <div className="processing-indicator">
        <div className="processing-spinner" />
        <span>Loading record...</span>
      </div>
    </div>
  );

  const cb = rec.confidence_breakdown;

  return (
    <div className="page">
      <Link to="/review" className="back-link">&larr; Back to Queue</Link>

      <div className="detail-header">
        <h1>{rec.metric || "Unknown Metric"}</h1>
        <div className="header-badges">
          <span className="badge-group">
            <span className="badge-label">Status</span>
            <StatusBadge label={rec.status} />
          </span>
          {rec.decision && (
            <span className="badge-group">
              <span className="badge-label">Decision</span>
              <span className="decision-badge-outline" data-decision={rec.decision}>
                {rec.decision.replace("_", " ")}
              </span>
            </span>
          )}
        </div>
      </div>

      <div className="card">
        <h2>Financial Data</h2>
        <div className="detail-grid">
          <div className="detail-field">
            <span className="field-label">Company</span>
            <span>{rec.company_id}</span>
          </div>
          <div className="detail-field">
            <span className="field-label">Metric</span>
            <span className="metric-pill">{rec.metric}</span>
          </div>
          <div className="detail-field">
            <span className="field-label">Value</span>
            <span style={{ fontSize: 18, fontWeight: 700, fontFamily: "var(--font-mono)" }}>
              {fmt(rec.value)}
            </span>
          </div>
          <div className="detail-field">
            <span className="field-label">Period</span>
            <span>{rec.normalized_period}</span>
          </div>
          <div className="detail-field">
            <span className="field-label">Version</span>
            <span>{rec.version}</span>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Source Traceability</h2>
        <div className="detail-grid">
          <div className="detail-field">
            <span className="field-label">File</span>
            <span style={{ fontSize: 12 }}>{rec.source_file}</span>
          </div>
          <div className="detail-field">
            <span className="field-label">Sheet</span>
            <span>{rec.sheet_name}</span>
          </div>
          <div className="detail-field">
            <span className="field-label">Cell</span>
            <span className="mono">{rec.cell_reference}</span>
          </div>
          <div className="detail-field">
            <span className="field-label">Raw label</span>
            <span className="mono">&quot;{rec.raw_label}&quot;</span>
          </div>
          <div className="detail-field">
            <span className="field-label">Mapped to</span>
            <span className="metric-pill">{rec.mapped_metric}</span>
          </div>
          <div className="detail-field">
            <span className="field-label">Method</span>
            <span>{rec.mapping_method}</span>
          </div>
          <div className="detail-field full-width">
            <span className="field-label">Mapping reason</span>
            <span style={{ fontSize: 12 }}>{rec.mapping_reason}</span>
          </div>
          <div className="detail-field">
            <span className="field-label">Raw period</span>
            <span className="mono">&quot;{rec.raw_period}&quot;</span>
          </div>
          <div className="detail-field">
            <span className="field-label">Normalized</span>
            <span>{rec.normalized_period} ({rec.period_type})</span>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Confidence Breakdown</h2>
        <div className="confidence-list">
          <ConfidenceBar value={cb.extraction} label="Extraction" />
          <ConfidenceBar value={cb.mapping} label="Mapping" />
          <ConfidenceBar value={cb.sanity} label="Sanity" />
          <ConfidenceBar value={cb.source} label="Source" />
          <ConfidenceBar value={cb.historical} label="Historical" />
          <div className="confidence-total">
            TOTAL: {rec.confidence_total.toFixed(2)}
          </div>
        </div>
      </div>

      {!rec.sanity_passed && rec.sanity_issues.length > 0 && (
        <div className="card card-error">
          <h2>Sanity Issues</h2>
          <ul>
            {rec.sanity_issues.map((issue, i) => (
              <li key={i}>{issue}</li>
            ))}
          </ul>
        </div>
      )}

      {rec.change_type !== "NEW" && (
        <div className="card">
          <h2>Change Detection</h2>
          <div className="detail-grid">
            <div className="detail-field">
              <span className="field-label">Type</span>
              <span>{rec.change_type}</span>
            </div>
            {rec.previous_value !== null && (
              <>
                <div className="detail-field">
                  <span className="field-label">Previous value</span>
                  <span>{fmt(rec.previous_value)}</span>
                </div>
                <div className="detail-field">
                  <span className="field-label">Delta</span>
                  <span>
                    {rec.delta !== null && (
                      <>
                        {rec.delta >= 0 ? "+" : ""}{fmt(rec.delta)}
                        {rec.delta_percent !== null && (
                          <> ({rec.delta_percent >= 0 ? "+" : ""}{rec.delta_percent}%)</>
                        )}
                      </>
                    )}
                  </span>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {rec.status === "PENDING" && (
        <div className="action-bar">
          <button className="btn-approve" disabled={acting} onClick={() => handleAction("APPROVE")}>
            Approve
          </button>
          <button className="btn-reject" disabled={acting} onClick={() => handleAction("REJECT")}>
            Reject
          </button>
          <button className="btn-investigate" disabled={acting} onClick={() => handleAction("INVESTIGATE")}>
            Investigate
          </button>
        </div>
      )}

      {actionDone && <div className="success-box">{actionDone}</div>}
    </div>
  );
}
