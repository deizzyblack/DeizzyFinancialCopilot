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
      <h1>Dashboard</h1>

      <div className="stat-row">
        <div className="stat-item">
          <span className="stat-num">{totalRecords}</span>
          <span className="stat-label">pending</span>
        </div>
        <div className="stat-item">
          <span className="stat-num" style={{ color: "var(--red-text)" }}>{flagCount}</span>
          <span className="stat-label">flagged</span>
        </div>
        <div className="stat-item">
          <span className="stat-num" style={{ color: "var(--green-text)" }}>
            {reviewCount > 0 ? reviewCount : 0}
          </span>
          <span className="stat-label">ready to review</span>
        </div>
      </div>

      <div className="stat-row" style={{ gap: 12 }}>
        <Link to="/upload" className="btn-primary" style={{ textDecoration: "none" }}>
          Upload Data
        </Link>
        <Link to="/review" className="btn-ghost" style={{ textDecoration: "none" }}>
          Review Queue
        </Link>
        <Link to="/analysis" className="btn-ghost" style={{ textDecoration: "none" }}>
          Company Analysis
        </Link>
      </div>

      {flagged && flagged.records.length > 0 && (
        <div className="card" style={{ marginTop: 8 }}>
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
                    <Link to={`/records/${r.record_id}`}>{r.metric ?? "Unknown"}</Link>
                  </td>
                  <td className="num">{r.value.toLocaleString()}</td>
                  <td className="reason-cell">{r.reason || "\u2014"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: 10 }}>
            <Link to="/review?filter=FLAG" style={{ fontSize: 12 }}>
              View all flagged
            </Link>
          </div>
        </div>
      )}

      {(!flagged || flagged.records.length === 0) && totalRecords === 0 && (
        <div className="card">
          <div className="empty-state">
            <p>No records yet.</p>
            <p className="help-text">
              <Link to="/upload">Upload a file</Link> to start processing financial data.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
