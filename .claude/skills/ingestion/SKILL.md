# Skill: Ingestion

## Description
Ingests Excel financial files, generates UUID file_id and SHA256 hash, detects duplicates, and stores file metadata. Prevents reprocessing of already-seen files.

## Trigger
When user uploads a financial file or requests file ingestion.

## Scope
- File intake and validation
- Duplicate detection via SHA256
- Metadata extraction (filename, size, mime_type, timestamp)
- Returns file_id and status (NEW or DUPLICATE)
