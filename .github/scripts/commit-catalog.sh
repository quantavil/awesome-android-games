#!/usr/bin/env bash
# Commit regenerated catalog files and push them to main.
#
# Usage: bash .github/scripts/commit-catalog.sh "<commit message>"
#
# A failed rebase or push exits non-zero, so the calling step fails and the
# problem is visible in the run logs instead of being silently skipped.
set -euo pipefail

message="${1:?commit message is required}"

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

git add games.json README.md
if git diff --staged --quiet; then
  echo "No catalog changes to commit."
  exit 0
fi

git commit -m "$message"
git pull --rebase origin main
git push origin HEAD:main
