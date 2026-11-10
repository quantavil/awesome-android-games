#!/usr/bin/env bash
# Commit regenerated catalog files and push them back to the checked-out branch.
#
# Usage: bash .github/scripts/commit-catalog.sh "<commit message>"
#
# The branch comes from GITHUB_REF_NAME (set by Actions) or the local HEAD, so a
# manual run on a feature branch updates that branch and never main.
# A failed rebase or push exits non-zero, so the calling step fails and the
# problem is visible in the run logs instead of being silently skipped.
set -euo pipefail

message="${1:?commit message is required}"
branch="${GITHUB_REF_NAME:-$(git rev-parse --abbrev-ref HEAD)}"
if [ -z "$branch" ] || [ "$branch" = "HEAD" ]; then
  echo "Refusing to commit: no branch is checked out." >&2
  exit 1
fi

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

git add games.json README.md
if git diff --staged --quiet; then
  echo "No catalog changes to commit."
  exit 0
fi

git commit -m "$message"
git pull --rebase origin "$branch"
git push origin "HEAD:$branch"
