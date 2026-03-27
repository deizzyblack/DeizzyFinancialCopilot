import { useState } from "react";
import { Link } from "react-router-dom";
import { ingestFile } from "../api";
import { StatusBadge } from "../components/StatusBadge";
import type { PipelineResult } from "../types";

export function UploadPage() {
  const [company, setCompany] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<PipelineResult | null>(null);

  async function handleUpload() {
    if (!file || !company.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await ingestFile(file, company.trim());
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  const grouped = result?.outcomes.reduce(
    (acc, o) => {
      const key = o.decision || "UNKNOWN";
      if (!acc[key]) acc[key] = [];
      acc[key].push(o);
      return acc;
    },
    {} as Record<string, typeof result.outcomes>,
  );

  const flagged = [
    ...(grouped?.FLAG ?? []),
    ...(grouped?.REVIEW_REQUIRED ?? []),
  ];

  return (
    <div className="page">
      <h1>Upload Financial Data</h1>

      <div className="card">
        <div className="form-row">
          <label>Company name</label>
          <input
            type="text"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="e.g. Acme Corp"
          />
        </div>
        <div className="form-row">
          <label>Excel file</label>
          <input
            type="file"
            accept=".xlsx,.xls"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>
        <button
          onClick={handleUpload}
          disabled={loading || !file || !company.trim()}
        >
          {loading ? "Processing..." : "Upload"}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      {result && (
        <div className="card">
          <h2>
            {result.status === "DUPLICATE"
              ? "Duplicate file detected"
              : `${result.records_created} records extracted from ${result.filename}`}
          </h2>

          {result.status === "COMPLETED" && grouped && (
            <>
              <div className="summary-bars">
                {(["AUTO_READY", "REVIEW_REQUIRED", "FLAG"] as const).map(
                  (key) => {
                    const count = grouped[key]?.length ?? 0;
                    if (count === 0) return null;
                    const pct =
                      result.records_created > 0
                        ? Math.round((count / result.records_created) * 100)
                        : 0;
                    return (
                      <div key={key} className="summary-row">
                        <StatusBadge label={key} />
                        <span>{count} records</span>
                        <div className="summary-track">
                          <div
                            className="summary-fill"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  },
                )}
              </div>

              {flagged.length > 0 && (
                <div className="issues-list">
                  <h3>Issues requiring attention:</h3>
                  <ul>
                    {flagged.map((o) => (
                      <li key={o.record_id}>
                        <strong>{o.metric ?? "Unknown"}</strong>: {o.reason}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <Link to="/review" className="btn">
                Go to Review Queue
              </Link>
            </>
          )}

          {result.errors.length > 0 && (
            <div className="error-box">
              {result.errors.map((e, i) => (
                <div key={i}>{e}</div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
