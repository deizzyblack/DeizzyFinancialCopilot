# Demo Datasets

Four Excel files designed to showcase the Financial Data Autopilot in a 5-minute demo.

## Files

### 1. `acme_q3_2025_clean.xlsx` — Clean Quarterly Report

**Company:** Acme Corp | **Period:** Q3-2025

| Metric | Value |
|--------|-------|
| Revenue | 12,500,000 |
| EBITDA | 3,200,000 |
| Net Income | 1,800,000 |
| Cash and Cash Equivalents | 4,500,000 |
| Total Assets | 28,000,000 |
| Total Equity | 15,000,000 |

**Expected behavior:** 6 records extracted, all with high confidence. Most should be AUTO_READY. Demonstrates the happy path — upload, review, approve.

---

### 2. `beta_q3_2025_messy.xlsx` — Messy Data with Real Problems

**Company:** Beta Inc | **Period:** 30.09.2025 (date format, not Q3-2025)

| Metric | Value | Issue |
|--------|-------|-------|
| Net Sales | 1,800,000 | Synonym for Revenue |
| EBITDA | 2,500,000 | **Exceeds Revenue (1.8M) — sanity fail** |
| Profit After Tax | 950,000 | Synonym for Net Income |
| Cash | 3,200,000 | Clean |
| Total Assets | 20,000,000 | **Not equal to Liab + Equity (17M) — sanity fail** |
| Total Liabilities | 8,000,000 | Part of balance sheet |
| Shareholders' Equity | 9,000,000 | Part of balance sheet |

**Expected behavior:** Multiple FLAG and REVIEW_REQUIRED records. EBITDA > Revenue is always caught. Balance sheet mismatch detected (Assets 20M vs Liabilities 8M + Equity 9M = 17M). Date-style period ("30.09.2025") is normalized to Q3-2025 by the regex parser.

---

### 3a. `acme_q3_2025_original.xlsx` — Original Report (for Revision Demo)

**Company:** Acme Corp | **Period:** Q3-2025

| Metric | Value |
|--------|-------|
| Revenue | 12,000,000 |
| EBITDA | 3,000,000 |
| Net Income | 1,600,000 |
| Cash and Cash Equivalents | 4,200,000 |
| Total Assets | 27,000,000 |
| Total Equity | 14,500,000 |

**Upload this first**, approve all records, then upload the revised version.

### 3b. `acme_q3_2025_revised.xlsx` — Revised Report

**Company:** Acme Corp | **Period:** Q3-2025

| Metric | Original | Revised | Change |
|--------|----------|---------|--------|
| Revenue | 12,000,000 | 13,500,000 | +1,500,000 (+12.5%) |
| Net Income | 1,600,000 | 2,100,000 | +500,000 (+31.3%) |
| Others | unchanged | unchanged | — |

**Expected behavior:** After uploading the revised file, change detection identifies REVISION records for Revenue and Net Income with version 2. The detail page shows the previous value, delta, and percentage change. Other metrics are flagged as DUPLICATE.

---

## Demo Flow

1. **Upload** `acme_q3_2025_clean.xlsx` as "Acme Corp" — show happy path
2. **Upload** `beta_q3_2025_messy.xlsx` as "Beta Inc" — show error detection
3. **Upload** `acme_q3_2025_original.xlsx` as "Acme Corp", approve all, then upload `acme_q3_2025_revised.xlsx` — show revision tracking
