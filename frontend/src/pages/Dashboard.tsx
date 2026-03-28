import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getPendingRecords } from "../api";
import type { PaginatedRecords } from "../types";

export function Dashboard() {
  const [data, setData] = useState<PaginatedRecords | null>(null);
  const [flagged, setFlagged] = useState<PaginatedRecords | null>(null);

  useEffect(() => {
    getPendingRecords(undefined, 1, 5).then(setData).catch(() => {});
    getPendingRecords("FLAG", 1, 5).then(setFlagged).catch(() => {});
  }, []);

  const totalRecords = data?.total ?? 0;
  const flagCount = flagged?.total ?? 0;
  const reviewCount = totalRecords - flagCount;

  return (
    <div className="page">
      <div className="hero-section">
        <h1 className="hero-title">
          Your <span className="gradient">Financial Data</span> Copilot
        </h1>
        <p className="hero-subtitle">
          Ingest, parse, validate, and trust your financial data. Automated quality scoring with full audit trail.
        </p>
      </div>

      {/* Pipeline visualization */}
      <div className="pipeline-bar">
        <span className="pipeline-step done">Ingest</span>
        <span className="pipeline-arrow">&rarr;</span>
        <span className="pipeline-step done">Parse</span>
        <span className="pipeline-arrow">&rarr;</span>
        <span className="pipeline-step done">Map</span>
        <span className="pipeline-arrow">&rarr;</span>
        <span className="pipeline-step done">Normalize</span>
        <span className="pipeline-arrow">&rarr;</span>
        <span className="pipeline-step done">Validate</span>
        <span className="pipeline-arrow">&rarr;</span>
        <span className="pipeline-step done">Score</span>
        <span className="pipeline-arrow">&rarr;</span>
        <span className="pipeline-step active">Decide</span>
        <span className="pipeline-arrow">&rarr;</span>
        <span className="pipeline-step">Audit</span>
      </div>

      {/* Stats */}
      <div className="stat-grid">
        <div className="stat-card">
          <span className="stat-value">{totalRecords}</span>
          <span className="stat-label">Pending Records</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{flagCount}</span>
          <span className="stat-label">Flagged Issues</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{reviewCount > 0 ? reviewCount : 0}</span>
          <span className="stat-label">Ready to Review</span>
        </div>
      </div>

      {/* Feature cards */}
      <div className="feature-grid">
        <Link to="/upload" className="feature-card" style={{ textDecoration: "none", color: "inherit" }}>
          <div className="feature-icon">+</div>
          <h3>Upload Data</h3>
          <p>Drop an Excel file to extract, map, and validate financial metrics automatically.</p>
        </Link>
        <Link to="/review" className="feature-card" style={{ textDecoration: "none", color: "inherit" }}>
          <div className="feature-icon">#</div>
          <h3>Review Queue</h3>
          <p>Review flagged records, approve auto-ready data, and investigate anomalies.</p>
        </Link>
        <Link to="/audit" className="feature-card" style={{ textDecoration: "none", color: "inherit" }}>
          <div className="feature-icon">~</div>
          <h3>Audit Trail</h3>
          <p>Full traceability for every data point. From raw cell to approved record.</p>
        </Link>
        <div className="feature-card" style={{ opacity: 0.5 }}>
          <div className="feature-icon">*</div>
          <h3>Benchmarking</h3>
          <p>Compare metrics across portfolio companies. Coming soon.</p>
        </div>
      </div>

      {/* Recent flagged records */}
      {flagged && flagged.records.length > 0 && (
        <div className="card">
          <h2>Recent Flagged Records</h2>
          <table className="data-table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Metric</th>
                <th className="num">Value</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {flagged.records.map((r) => (
                <tr key={r.record_id}>
                  <td>{r.company_id}</td>
                  <td>
                    <Link to={`/records/${r.record_id}`}>
                      {r.metric ?? "Unknown"}
                    </Link>
                  </td>
                  <td className="num">{r.value.toLocaleString()}</td>
                  <td className="reason-cell">{r.reason || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: 12 }}>
            <Link to="/review?filter=FLAG" className="btn btn-ghost">
              View all flagged
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
