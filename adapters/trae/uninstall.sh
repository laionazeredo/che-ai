#!/usr/bin/env bash
#
# adapters/trae/uninstall.sh — rollback the Trae IDE adapter.
#
# Removes ONLY the symlinks this adapter created (i.e. those whose resolved
# target lives inside this Che checkout, $CHE_REPO). Trae-native artifacts and
# any user-owned real files are NEVER touched. Restores .bak pointers when a
# backup was left behind by install.sh.
#
# Scope mirrors adapters/trae/install.sh:
#   • AGENTS.md / CHE_RULES.md / CHE_COMMANDS.md  (file symlinks)
#   • domains/  user_rules/                        (dir symlinks)
#   • skills/<item>   commands/<item>   hooks/<item>  (per-item symlinks)
#   • hooks.json                                   (rendered file)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHE_REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"

TRAE_HOME="${TRAE_HOME:-$HOME/.trae}"

echo "Uninstalling Che Trae adapter..."
echo "Che repo  : $CHE_REPO"
echo "Trae home : $TRAE_HOME"

if [ ! -d "$TRAE_HOME" ]; then
  echo "SKIP: Trae home not found at $TRAE_HOME. Nothing to remove."
  exit 0
fi

# is_che_link <path> — true only if it is a symlink resolving inside $CHE_REPO.
is_che_link() {
  local target="$1"
  [ -L "$target" ] || return 1
  local resolved
  resolved="$(readlink -f "$target" 2>/dev/null || true)"
  case "$resolved" in
    "$CHE_REPO"/*) return 0 ;;
    *) return 1 ;;
  esac
}

# 1. Root pointer files + rule directories (restore .bak when present).
unlink_pointer() {
  local dst="$1" label="$2"
  if is_che_link "$dst"; then
    rm "$dst"
    if [ -e "${dst}.bak" ]; then
      mv "${dst}.bak" "$dst"
      echo "  ← $label (restored .bak)"
    else
      echo "  ← $label"
    fi
  fi
}

unlink_pointer "$TRAE_HOME/AGENTS.md"       "AGENTS.md"
unlink_pointer "$TRAE_HOME/CHE_RULES.md"    "CHE_RULES.md"
unlink_pointer "$TRAE_HOME/CHE_COMMANDS.md" "CHE_COMMANDS.md"
unlink_pointer "$TRAE_HOME/domains"         "domains/"
unlink_pointer "$TRAE_HOME/user_rules"      "user_rules/"

# 2. Per-item collections.
unlink_collection() {
  local dir="$1" label="$2" removed=0 target
  [ -d "$dir" ] || { echo "$label removed: 0"; return 0; }
  for target in "$dir"/*; do
    is_che_link "$target" || continue
    rm "$target"
    removed=$((removed + 1))
  done
  echo "$label removed: $removed"
}

unlink_collection "$TRAE_HOME/skills"   "Skill links  "
unlink_collection "$TRAE_HOME/commands" "Command links"
unlink_collection "$TRAE_HOME/hooks"    "Hook links   "

# 3. Rendered hooks.json (only when it was rendered by us — i.e. not a symlink).
HOOKS_CONFIG="$TRAE_HOME/hooks.json"
if [ -f "$HOOKS_CONFIG" ] && [ ! -L "$HOOKS_CONFIG" ]; then
  HOOKS_BKP="${HOOKS_CONFIG}.removed-$(date +%Y%m%d-%H%M%S)"
  mv "$HOOKS_CONFIG" "$HOOKS_BKP"
  echo "hooks.json moved → $HOOKS_BKP"
fi

echo
echo "Che — Trae adapter removed successfully."
