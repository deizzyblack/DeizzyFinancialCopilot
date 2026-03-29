import { useState, useRef } from "react";
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
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

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

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f && (f.name.endsWith(".xlsx") || f.name.endsWith(".xls"))) {
      setFile(f);
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

  const autoCount = grouped?.AUTO_READY?.length ?? 0;
  const reviewCount = grouped?.REVIEW_REQUIRED?.length ?? 0;
  const flagCount = grouped?.FLAG?.length ?? 0;

  function nextStepMessage(): string {
    if (!result || result.status !== "COMPLETED") return "";
    if (result.records_created === 0) return "No financial records found in this file.";
    const parts: string[] = [];
    if (autoCount > 0) parts.push(`${autoCount} auto-ready`);
    if (reviewCount > 0) parts.push(`${reviewCount} need review`);
    if (flagCount > 0) parts.push(`${flagCount} flagged`);
    return parts.join(", ") + ".";
  }

  return (
    <div className="page">
      <h1>Upload</h1>

      <div className="card">
        <div className="form-row">
          <label>Company</label>
          <input
            type="text"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="e.g. Acme Corp"
          />
        </div>

        <div
          className={`upload-zone ${dragging ? "dragging" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileRef.current?.click()}
        >
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xls"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            style={{ display: "none" }}
          />
          {file ? (
            <>
              <div className="upload-text">{file.name}</div>
              <div className="upload-hint">{(file.size / 1024).toFixed(0)} KB</div>
            </>
          ) : (
            <>
              <div className="upload-text">Drop Excel file here or click to browse</div>
              <div className="upload-hint">.xlsx or .xls</div>
            </>
          )}
        </div>

        {loading ? (
          <div className="processing-indicator">
            <div className="processing-spinner" />
            <span>Processing...</span>
          </div>
        ) : (
          <button
            className="btn-primary"
            onClick={handleUpload}
            disabled={!file || !company.trim()}
          >
            Process File
          </button>
        )}
      </div>

      {error && <div className="error-box">{error}</div>}

      {result && (
        <div className="card">
          <h2>
            {result.status === "DUPLICATE"
              ? "Duplicate detected"
              : `${result.records_created} records extracted`}
          </h2>

          {result.status === "COMPLETED" && grouped && (
            <>
              <div className="upload-summary-line">
                {nextStepMessage()}
              </div>

              <div className="summary-bars">
                {(["AUTO_READY", "REVIEW_REQUIRED", "FLAG"] as const).map((key) => {
                  const count = grouped[key]?.length ?? 0;
                  if (count === 0) return null;
                  const pct = result.records_created > 0
                    ? Math.round((count / result.records_created) * 100) : 0;
                  return (
                    <div key={key} className="summary-row">
                      <StatusBadge label={key} />
                      <span style={{ fontSize: 12, color: "var(--text-muted)", minWidth: 60 }}>
                        {count} records
                      </span>
                      <div className="summary-track">
                        <div className="summary-fill" data-type={key} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>

              {flagged.length > 0 && (
                <div className="issues-list">
                  <h3>Issues</h3>
                  <ul>
                    {flagged.slice(0, 10).map((o) => (
                      <li key={o.record_id}>
                        <strong>{o.metric ?? "Unknown"}</strong>: {o.reason}
                      </li>
                    ))}
                    {flagged.length > 10 && (
                      <li style={{ background: "transparent", border: "none", color: "var(--text-muted)" }}>
                        +{flagged.length - 10} more
                      </li>
                    )}
                  </ul>
                </div>
              )}

              <div className="next-step-box">
                <Link to="/review" className="btn-primary" style={{ textDecoration: "none" }}>
                  Review records
                </Link>
              </div>
            </>
          )}

          {result.status === "DUPLICATE" && (
            <p className="help-text">
              This file has already been processed. Check the{" "}
              <Link to="/audit">audit trail</Link> for details.
            </p>
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
