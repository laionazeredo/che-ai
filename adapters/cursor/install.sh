#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHE_REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Cursor uses a different approach: usually project-level .cursorrules or .cursor/rules/
# We will provide a way to link Che skills to a project's .cursor/rules folder.

echo "Che repo : $CHE_REPO"

# Note: There is no standard global path for Cursor rules like ~/.agents/skills
# but we can create a symlink in the project root during install-che.sh if we detect Cursor.

echo
echo "Cursor Che adapter ready."
echo "To use Che in a Cursor project, run:"
echo "  ln -sfn $CHE_REPO/adapters/cursor/AGENTS.md ./AGENTS.md"
echo "  mkdir -p .cursor/rules"
echo "  ln -sfn $CHE_REPO/skills/* .cursor/rules/"
echo
echo "For global rules, copy the content of $CHE_REPO/adapters/cursor/AGENTS.md"
echo "to Cursor Settings > General > Rules for AI."
