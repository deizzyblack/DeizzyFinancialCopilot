# Financial Data Autopilot - CLAUDE.md

## Project Overview
Financial Data Autopilot System — ingests, parses, maps, validates, and acts on financial data with controlled automation and full traceability.

## Tech Stack
- **Backend**: Python 3.11+, FastAPI
- **Database**: PostgreSQL, SQLAlchemy ORM, Alembic migrations
- **Data Processing**: Pandas, openpyxl
- **LLM**: External API (fallback only, never primary)
- **Testing**: pytest
- **Linting**: ruff

## Directory Structure
```
src/
  ingestion/       # M1 - File intake, dedup, metadata
  parser/          # M2 - Excel extraction
  mapping/         # M3 - Semantic label → metric mapping
  period/          # M4 - Period normalization (Q1, H1, FY, etc.)
  normalization/   # M5 - Unified candidate records
  storage/         # M6 - Append-only storage + status management
  change_detection/# M7 - Diff vs last APPROVED record
  sanity/          # M8 - Deterministic validation rules
  source_reliability/ # M9 - Source trust scoring
  confidence/      # M10 - Confidence scoring (deterministic rubric)
  decision/        # M11 - Auto/review/flag routing
  action/          # M12 - Action recommendation generator
  execution/       # M14 - Approve/reject execution
  audit/           # M15 - Full audit trail
  api/             # FastAPI routes
  models/          # SQLAlchemy models
  core/            # Shared config, deps, enums
tests/             # pytest test suite
alembic/           # DB migrations
uploads/           # Ingested file storage
```

## Commands
- `build`: `pip install -e ".[dev]"`
- `test`: `pytest tests/ -v`
- `lint`: `ruff check src/ tests/`
- `format`: `ruff format src/ tests/`
- `migrate`: `alembic upgrade head`
- `run`: `uvicorn src.api.main:app --reload`

## Architecture Rules
1. **Append-only storage** — NEVER delete/overwrite financial records
2. **Status lifecycle**: PENDING → APPROVED | REJECTED
3. **No AI in parsing** — deterministic extraction only
4. **LLM is fallback** — rule-based first, LLM only when rules fail
5. **Full traceability** — every action logged in audit trail
6. **Confidence gating** — low confidence NEVER auto-approved

## Module Pipeline Flow
```
Ingest → Parse → Map → Normalize → Store(PENDING) → ChangeDetect → Sanity → Confidence → Decision → Action → User → Execute → Audit
```

## Gotchas
- Q2 != H1 != YTD != FY — period types are distinct
- EBITDA > Revenue is always an error
- Assets must equal Liabilities + Equity
- Duplicate files detected by SHA256 hash
- Column headers in Excel may contain dates, periods, or garbage
- Mapping memory is per-company — same label can map differently
