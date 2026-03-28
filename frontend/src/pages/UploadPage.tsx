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
    if (autoCount > 0) parts.push(`${autoCount} record${autoCount > 1 ? "s are" : " is"} auto-ready and awaiting approval`);
    if (reviewCount > 0) parts.push(`${reviewCount} record${reviewCount > 1 ? "s need" : " needs"} your review`);
    if (flagCount > 0) parts.push(`${flagCount} record${flagCount > 1 ? "s are" : " is"} flagged with issues`);
    return parts.join(". ") + ".";
  }

  function ctaLabel(): string {
    if (flagCount > 0) return "Review flagged records";
    if (reviewCount > 0) return "Review records";
    return "Review and approve records";
  }

  return (
    <div className="page">
      <h1>Upload Financial Data</h1>
      <p className="page-subtitle">Drop an Excel file to extract and validate financial metrics</p>

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
          <div className="upload-icon">+</div>
          {file ? (
            <>
              <div className="upload-text">{file.name}</div>
              <div className="upload-hint">{(file.size / 1024).toFixed(0)} KB</div>
            </>
          ) : (
            <>
              <div className="upload-text">Drop your Excel file here</div>
              <div className="upload-hint">.xlsx or .xls files supported</div>
            </>
          )}
        </div>

        {loading ? (
          <div className="processing-indicator">
            <div className="processing-spinner" />
            <span className="processing-text">Processing file through pipeline...</span>
          </div>
        ) : (
          <button
            onClick={handleUpload}
            disabled={!file || !company.trim()}
            style={{ marginTop: 16 }}
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
              ? "Duplicate file detected"
              : `${result.records_created} records extracted`}
          </h2>

          {result.status === "COMPLETED" && grouped && (
            <>
              {/* Stat pills */}
              <div className="stat-grid" style={{ marginBottom: 16 }}>
                {autoCount > 0 && (
                  <div className="stat-card" style={{ borderLeft: "3px solid var(--green)" }}>
                    <span className="stat-value" style={{ fontSize: 24 }}>{autoCount}</span>
                    <span className="stat-label">Auto-Ready</span>
                  </div>
                )}
                {reviewCount > 0 && (
                  <div className="stat-card" style={{ borderLeft: "3px solid var(--yellow)" }}>
                    <span className="stat-value" style={{ fontSize: 24 }}>{reviewCount}</span>
                    <span className="stat-label">Needs Review</span>
                  </div>
                )}
                {flagCount > 0 && (
                  <div className="stat-card" style={{ borderLeft: "3px solid var(--red)" }}>
                    <span className="stat-value" style={{ fontSize: 24 }}>{flagCount}</span>
                    <span className="stat-label">Flagged</span>
                  </div>
                )}
              </div>

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
                            data-type={key}
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
                    {flagged.slice(0, 10).map((o) => (
                      <li key={o.record_id}>
                        <strong>{o.metric ?? "Unknown"}</strong>: {o.reason}
                      </li>
                    ))}
                    {flagged.length > 10 && (
                      <li style={{ background: "transparent", border: "none", color: "var(--text-muted)" }}>
                        +{flagged.length - 10} more issues
                      </li>
                    )}
                  </ul>
                </div>
              )}

              <div className="next-step-box">
                <p>{nextStepMessage()}</p>
                <Link to="/review" className="btn">
                  {ctaLabel()}
                </Link>
              </div>
            </>
          )}

          {result.status === "DUPLICATE" && (
            <p className="help-text">
              This file has already been processed. Upload a different file or check the{" "}
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
