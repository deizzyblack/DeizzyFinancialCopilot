import { useEffect, useState } from "react";
import { getBenchmarking } from "../api";
import type { BenchmarkingResult } from "../types";

const METRICS = ["", "Revenue", "EBITDA", "Gross Profit", "Net Income", "Cash", "Assets", "Liabilities", "Equity"];

function fmt(n: number): string {
  if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (Math.abs(n) >= 1_000) return (n / 1_000).toFixed(0) + "K";
  return n.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

export function Benchmarking() {
  const [data, setData] = useState<BenchmarkingResult | null>(null);
  const [metric, setMetric] = useState("");
  const [period, setPeriod] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setError("");
    getBenchmarking(metric || undefined, period || undefined)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [metric, period]);

  return (
    <div className="page">
      <h1>Portfolio Benchmarking</h1>
      <p className="page-subtitle">Compare financial metrics across portfolio companies</p>

      <div className="filter-bar">
        <select value={metric} onChange={(e) => setMetric(e.target.value)}>
          <option value="">All Metrics</option>
          {METRICS.filter(Boolean).map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Period (e.g. Q3-2025)"
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
        />
      </div>

      {error && <div className="error-box">{error}</div>}

      {data && data.companies.length === 0 && (
        <div className="card empty-state">
          <div className="empty-state-icon">*</div>
          <p>No approved records to compare</p>
          <p className="help-text">
            Approve records in the review queue to see cross-company benchmarking.
          </p>
        </div>
      )}

      {data && data.companies.length > 0 && (
        <>
          <div className="stat-grid">
            <div className="stat-card">
              <span className="stat-value">{data.total_companies}</span>
              <span className="stat-label">Companies</span>
            </div>
            <div className="stat-card">
              <span className="stat-value">
                {data.companies.reduce((sum, c) => sum + c.record_count, 0)}
              </span>
              <span className="stat-label">Approved Records</span>
            </div>
            <div className="stat-card">
              <span className="stat-value">
                {new Set(data.companies.flatMap((c) => c.metrics)).size}
              </span>
              <span className="stat-label">Unique Metrics</span>
            </div>
          </div>

          {data.companies.map((company) => (
            <div key={company.company_id} className="card">
              <h2>{company.company_id}</h2>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th className="num">Value</th>
                    <th>Period</th>
                    <th>Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {company.records.map((r, i) => (
                    <tr key={i}>
                      <td><span className="metric-pill">{r.metric}</span></td>
                      <td className="num">{fmt(r.value)}</td>
                      <td>{r.period}</td>
                      <td>
                        <span style={{
                          color: r.confidence >= 0.85 ? "var(--green)" : r.confidence >= 0.5 ? "var(--yellow)" : "var(--red)",
                          fontFamily: "var(--font-mono)",
                          fontSize: 13,
                        }}>
                          {(r.confidence * 100).toFixed(0)}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
