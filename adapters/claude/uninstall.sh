#!/usr/bin/env bash
set -euo pipefail

CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
SKILLS_TARGET="$CLAUDE_HOME/skills"
COMMANDS_TARGET="$CLAUDE_HOME/commands"

echo "Uninstalling Claude Code Che adapter..."

# Remove AGENTS.md if it's a symlink
if [ -L "$CLAUDE_HOME/CLAUDE.md" ]; then
  rm "$CLAUDE_HOME/CLAUDE.md"
  if [ -e "$CLAUDE_HOME/CLAUDE.md.bak" ]; then
    mv "$CLAUDE_HOME/CLAUDE.md.bak" "$CLAUDE_HOME/CLAUDE.md"
  fi
fi

# Remove skill symlinks
if [ -d "$SKILLS_TARGET" ]; then
  find "$SKILLS_TARGET" -maxdepth 1 -type l -delete
fi

# Remove command symlinks
if [ -d "$COMMANDS_TARGET" ]; then
  find "$COMMANDS_TARGET" -maxdepth 1 -type l -delete
fi

# Remove hooks from settings.json
SETTINGS_PATH="$CLAUDE_HOME/settings.json"
if [ -f "$SETTINGS_PATH" ]; then
  python3 - "$SETTINGS_PATH" <<'PY'
import json
import sys
from pathlib import Path

settings_path = Path(sys.argv[1])
if not settings_path.exists():
    sys.exit(0)

try:
    with open(settings_path, "r") as f:
        settings = json.load(f)
except Exception:
    sys.exit(0)

if "hooks" in settings:
    del settings["hooks"]

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
PY
fi

echo "Uninstalled successfully."
