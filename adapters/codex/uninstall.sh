#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHE_REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
AGENTS_HOME="${AGENTS_HOME:-$HOME/.agents}"
SKILLS_TARGET="$AGENTS_HOME/skills"
COMMANDS_TARGET="$CODEX_HOME/commands"

echo "Uninstalling Codex Che adapter..."

# 1. Remove AGENTS.md
if [ -L "$CODEX_HOME/AGENTS.md" ]; then
  rm "$CODEX_HOME/AGENTS.md"
  if [ -e "$CODEX_HOME/AGENTS.md.bak" ]; then
    mv "$CODEX_HOME/AGENTS.md.bak" "$CODEX_HOME/AGENTS.md"
  fi
fi

# 2. Remove skill symlinks
REMOVED_SKILLS=0
if [ -d "$SKILLS_TARGET" ]; then
  for target in "$SKILLS_TARGET"/*; do
    [ -L "$target" ] || continue
    resolved="$(readlink -f "$target" 2>/dev/null || true)"
    case "$resolved" in
      "$CHE_REPO"/skills/*)
        rm "$target"
        REMOVED_SKILLS=$((REMOVED_SKILLS + 1))
        ;;
    esac
  done
fi

# 3. Remove command symlinks
REMOVED_COMMANDS=0
if [ -d "$COMMANDS_TARGET" ]; then
  for target in "$COMMANDS_TARGET"/*; do
    [ -L "$target" ] || continue
    resolved="$(readlink -f "$target" 2>/dev/null || true)"
    case "$resolved" in
      "$CHE_REPO"/commands/*)
        rm "$target"
        REMOVED_COMMANDS=$((REMOVED_COMMANDS + 1))
        ;;
    esac
  done
fi

# 4. Remove hooks.json
if [ -f "$CODEX_HOME/hooks.json" ]; then
  rm "$CODEX_HOME/hooks.json"
fi

# 5. Disable hooks in config.toml
CONFIG_TOML="$CODEX_HOME/config.toml"
if [ -f "$CONFIG_TOML" ]; then
  sed -i '/hooks = true/d' "$CONFIG_TOML"
fi

echo
echo "Codex Che adapter removed successfully."
echo "Skill links removed  : $REMOVED_SKILLS"
echo "Command links removed: $REMOVED_COMMANDS"
