# Skill: Parsing

## Description
Parses Excel workbooks to extract structured candidate financial data including raw labels, values, sheet names, cell references, and column headers. Uses deterministic extraction only — no AI.

## Trigger
When a file has been ingested and needs data extraction.

## Scope
- Excel workbook loading via openpyxl
- Sheet detection by financial keywords
- Cell-level extraction with full provenance
- Returns list of raw extracted records
