#!/bin/bash
# PostToolUse hook: Validate project structure integrity
# Ensures critical directories and files exist

REQUIRED_DIRS=("src" "tests" "alembic" "uploads")
REQUIRED_FILES=("CLAUDE.md" "pyproject.toml")

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "WARNING: Required directory '$dir' is missing."
    fi
done

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "WARNING: Required file '$file' is missing."
    fi
done

exit 0
