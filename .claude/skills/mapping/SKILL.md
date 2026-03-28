# Skill: Mapping

## Description
Maps raw financial labels from Excel cells to standardized metrics (Revenue, EBITDA, Net Income, Cash, Assets, Liabilities, Equity). Uses deterministic synonym matching first, company-approved memory second, LLM fallback last.

## Trigger
When extracted records need label-to-metric normalization, or when mapping false positives need correction.

## Scope
- SYNONYM_MAP: 44 canonical label → metric mappings
- Company-approved mappings from MappingMemory table
- Partial match with exclusion rules to prevent false positives
- LLM fallback with 0.8x confidence scaling
- Mapping rejection tracking (append-only negative signals)
- Returns MappingResult with metric, score, method, and reason
