import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getPendingRecords } from "../api";
import { ConfidenceBar } from "../components/ConfidenceBar";
import { StatusBadge } from "../components/StatusBadge";
import type { PaginatedRecords } from "../types";

const FILTERS = ["", "FLAG", "REVIEW_REQUIRED", "AUTO_READY"];
const FILTER_LABELS: Record<string, string> = {
  "": "All",
  FLAG: "Flagged",
  REVIEW_REQUIRED: "Needs Review",
  AUTO_READY: "Auto-Ready",
};

function fmt(n: number): string {
  return n.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

export function ReviewQueue() {
  const [data, setData] = useState<PaginatedRecords | null>(null);
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");

  useEffect(() => {
    setError("");
    getPendingRecords(filter || undefined, page, 25)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [filter, page]);

  const totalPages = data ? Math.ceil(data.total / data.per_page) : 0;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Review Queue</h1>
        <div className="filter-tabs">
          {FILTERS.map((f) => (
            <button
              key={f}
              className={`tab ${filter === f ? "active" : ""}`}
              onClick={() => {
                setFilter(f);
                setPage(1);
              }}
            >
              {FILTER_LABELS[f]}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      {data && data.records.length === 0 && (
        <div className="card empty-state">
          <p>No records to review.</p>
          <p className="help-text">
            <Link to="/">Upload a file</Link> to get started, or change the filter above.
          </p>
        </div>
      )}

      {data && data.records.length > 0 && (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Metric</th>
                <th className="num">Value</th>
                <th>Period</th>
                <th>Confidence</th>
                <th>Decision</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {data.records.map((r) => (
                <tr key={r.record_id}>
                  <td>{r.company_id}</td>
                  <td>
                    <Link to={`/records/${r.record_id}`}>
                      {r.metric ?? "Unknown"}
                    </Link>
                  </td>
                  <td className="num">{fmt(r.value)}</td>
                  <td>{r.normalized_period}</td>
                  <td>
                    <ConfidenceBar value={r.confidence} showValue />
                  </td>
                  <td>
                    <StatusBadge label={r.decision} />
                  </td>
                  <td className="reason-cell">{r.reason || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="pagination">
            <span>
              Showing {data.records.length} of {data.total} records
            </span>
            <div className="page-buttons">
              <button disabled={page <= 1} onClick={() => setPage(page - 1)}>
                Prev
              </button>
              <span>
                Page {page} of {totalPages || 1}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
