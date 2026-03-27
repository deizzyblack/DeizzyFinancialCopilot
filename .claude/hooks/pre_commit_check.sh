#!/bin/bash
# PreToolUse hook: Validate before committing
# Exit 0 = allow, Exit 2 = block

# Check that no .env files are being committed
if git diff --cached --name-only | grep -q '\.env'; then
    echo "BLOCKED: .env file detected in staging area. Remove it before committing."
    exit 2
fi

# Check that no credentials files are being committed
if git diff --cached --name-only | grep -qE '(credentials|secrets|\.key|\.pem)'; then
    echo "BLOCKED: Potential credentials file detected. Remove it before committing."
    exit 2
fi

exit 0
