# Skill: Testing

## Description
Generates and runs unit tests for Financial Data Autopilot modules using pytest. Covers ingestion, parsing, mapping, normalization, and validation logic with deterministic assertions.

## Trigger
When user requests tests, after implementing a module, or before committing.

## Scope
- Unit tests for each module in src/
- Integration tests for pipeline flow
- Uses pytest fixtures and tmp_path for file handling
- Mocks external dependencies (DB, LLM API)
