#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHE_REPO="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "--- Che Multi-Agent Setup ---"
echo "Che Repo: $CHE_REPO"

# 1. Setup Codex if installed
if command -v codex >/dev/null 2>&1; then
  echo "Detected Codex CLI. Installing adapter..."
  "$CHE_REPO/adapters/codex/install.sh"
else
  echo "Codex CLI not detected. Skipping."
fi

# 2. Setup Claude Code if installed
if command -v claude >/dev/null 2>&1; then
  echo "Detected Claude Code. Installing adapter..."
  "$CHE_REPO/adapters/claude/install.sh"
else
  echo "Claude Code not detected. Skipping."
fi

# 3. Setup Cursor adapter
if command -v cursor >/dev/null 2>&1 || [ -d "/Applications/Cursor.app" ] || [ -d "$HOME/.cursor" ]; then
  echo "Detected Cursor IDE. Preparing adapter..."
  "$CHE_REPO/adapters/cursor/install.sh"
else
  echo "Cursor IDE not detected. Skipping."
fi

# 4. Setup Trae (Default)
# Trae uses the repository root directly, so no linking needed, 
# but we can ensure global rules are set if needed.

echo "--- Setup Complete ---"
