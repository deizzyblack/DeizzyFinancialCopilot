import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getAuditLog } from "../api";
import type { PaginatedAudit } from "../types";

export function AuditLog() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState<PaginatedAudit | null>(null);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const fileId = searchParams.get("file_id") ?? "";
  const recordId = searchParams.get("record_id") ?? "";
  const eventType = searchParams.get("event_type") ?? "";
  const page = Number(searchParams.get("page") ?? "1");

  useEffect(() => {
    setError("");
    getAuditLog({
      fileId: fileId || undefined,
      recordId: recordId || undefined,
      eventType: eventType || undefined,
      page,
      perPage: 25,
    })
      .then(setData)
      .catch((e) => setError(e.message));
  }, [fileId, recordId, eventType, page]);

  function updateFilter(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    next.set("page", "1");
    setSearchParams(next);
  }

  function toggleExpand(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const totalPages = data ? Math.ceil(data.total / data.per_page) : 0;

  function setPage(p: number) {
    const next = new URLSearchParams(searchParams);
    next.set("page", String(p));
    setSearchParams(next);
  }

  return (
    <div className="page">
      <h1>Audit Trail</h1>

      <div className="filter-bar">
        <input
          type="text"
          placeholder="File ID"
          value={fileId}
          onChange={(e) => updateFilter("file_id", e.target.value)}
        />
        <input
          type="text"
          placeholder="Record ID"
          value={recordId}
          onChange={(e) => updateFilter("record_id", e.target.value)}
        />
        <select
          value={eventType}
          onChange={(e) => updateFilter("event_type", e.target.value)}
        >
          <option value="">All events</option>
          <option value="FILE_INGESTED">FILE_INGESTED</option>
          <option value="DATA_PARSED">DATA_PARSED</option>
          <option value="METRIC_MAPPED">METRIC_MAPPED</option>
          <option value="RECORD_CREATED">RECORD_CREATED</option>
          <option value="SANITY_CHECK">SANITY_CHECK</option>
          <option value="CONFIDENCE_SCORED">CONFIDENCE_SCORED</option>
          <option value="DECISION_MADE">DECISION_MADE</option>
          <option value="USER_ACTION">USER_ACTION</option>
          <option value="RECORD_APPROVED">RECORD_APPROVED</option>
          <option value="RECORD_REJECTED">RECORD_REJECTED</option>
        </select>
      </div>

      {error && <div className="error-box">{error}</div>}

      {data && (
        <>
          <div className="audit-list">
            {data.entries.map((entry) => (
              <div key={entry.id} className="audit-entry">
                <div
                  className="audit-row"
                  onClick={() => toggleExpand(entry.id)}
                >
                  <span className="audit-time">
                    {new Date(entry.timestamp).toLocaleString()}
                  </span>
                  <span className="audit-type">{entry.event_type}</span>
                  <span className="audit-ref">
                    {entry.record_id && (
                      <Link
                        to={`/records/${entry.record_id}`}
                        onClick={(e) => e.stopPropagation()}
                      >
                        Record
                      </Link>
                    )}
                  </span>
                  <span className="audit-expand">
                    {expanded.has(entry.id) ? "[-]" : "[+]"}
                  </span>
                </div>
                {expanded.has(entry.id) && (
                  <pre className="audit-details">
                    {JSON.stringify(entry.details, null, 2)}
                  </pre>
                )}
              </div>
            ))}
            {data.entries.length === 0 && (
              <div className="card empty-state">
                <p>No audit events yet.</p>
                <p className="help-text">
                  <Link to="/">Process a file</Link> to see the audit trail, or clear
                  the filters above.
                </p>
              </div>
            )}
          </div>

          <div className="pagination">
            <span>
              Showing {data.entries.length} of {data.total} entries
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
