#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHE_REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
AGENTS_HOME="${AGENTS_HOME:-$HOME/.agents}"
SKILLS_TARGET="$AGENTS_HOME/skills"

AGENTS_TARGET="$CODEX_HOME/AGENTS.md"
AGENTS_SOURCE="$SCRIPT_DIR/AGENTS.md"

REMOVED=0

if [ -L "$AGENTS_TARGET" ] &&
   [ "$(readlink -f "$AGENTS_TARGET")" = "$(readlink -f "$AGENTS_SOURCE")" ]; then
  rm "$AGENTS_TARGET"
  echo "Removed: $AGENTS_TARGET"
fi

if [ -d "$SKILLS_TARGET" ]; then
  for target in "$SKILLS_TARGET"/*; do
    [ -L "$target" ] || continue

    resolved="$(readlink -f "$target" 2>/dev/null || true)"

    case "$resolved" in
      "$CHE_REPO"/skills/*)
        rm "$target"
        echo "Removed: $target"
        REMOVED=$((REMOVED + 1))
        ;;
    esac
  done
fi

echo
echo "Codex Che adapter removed."
echo "Skill links removed: $REMOVED"
