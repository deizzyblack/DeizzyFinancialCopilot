# Skill: Validation

## Description
Validates financial records through sanity checks and confidence scoring. Sanity checks enforce deterministic rules (EBITDA ≤ Revenue, Assets = Liabilities + Equity). Confidence scoring combines extraction, mapping, sanity, source, and historical signals into a 0-1 score.

## Trigger
When normalized records need quality validation before decision routing.

## Scope
- Balance sheet identity: Assets = Liabilities + Equity
- Income statement bounds: EBITDA ≤ Revenue, Net Income ≤ EBITDA
- Confidence formula: 0.25 extraction + 0.20 mapping + 0.25 sanity + 0.15 source + 0.15 historical
- Decision thresholds: ≥0.85 AUTO_READY, 0.5–0.85 REVIEW_REQUIRED, <0.5 FLAG
- All results persisted on FinancialRecord for API serving
