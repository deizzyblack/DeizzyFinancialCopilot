# Skill: Noise Filter

## Description
Filters noise from raw Excel extraction before candidate record creation. Removes zero-value cells, adjustment columns, and percentage labels to reduce data volume while preserving all financial signal. Reports skip counts for traceability.

## Trigger
When a parsed Excel file produces excessive records, or when data quality analysis shows high noise-to-signal ratio.

## Scope
- Zero-value suppression: skip cells where abs(value) < 0.01
- Adjustment column exclusion: skip columns with "Adj" headers
- Percentage label demotion: skip labels containing %, margin, growth rate
- Skip counts returned in pipeline result for auditability
- Raw file preserved in uploads/ as source of truth
- Does NOT violate append-only: prevents creation, never deletes
