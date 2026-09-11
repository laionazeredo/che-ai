#!/usr/bin/env bash
#
# adapters/trae/install.sh — Trae IDE adapter (symlink-based, per-item).
#
# Wires the Che source-of-truth checkout ($CHE_REPO) into the Trae agent home
# ($HOME/.trae) using SYMLINKS ONLY — never copies repository content into the
# Trae home. Trae-native artifacts (builtin/, builtin_skills/, mcps/, memory/,
# permission/, toolhost/, trae-browser-screenshots/, workspace/, *.json native
# config) are NEVER touched.
#
# Idempotent: re-running only refreshes symlink targets and re-renders hooks.json.
#
# Injection points (all non-destructive):
#   • AGENTS.md                    → $CHE_REPO/AGENTS.md          (file symlink)
#   • CHE_RULES.md                 → $CHE_REPO/CHE_RULES.md       (file symlink)
#   • CHE_COMMANDS.md              → $CHE_REPO/CHE_COMMANDS.md    (file symlink)
#   • domains/                     → $CHE_REPO/domains/           (dir symlink)
#   • user_rules/                  → $CHE_REPO/user_rules/        (dir symlink)
#   • commands/<cmd>.md            → $CHE_REPO/commands/<cmd>.md  (per item)
#   • skills/<skill>/              → $CHE_REPO/skills/<skill>/    (per item)
#   • hooks/<hook>.py              → $CHE_REPO/hooks/<hook>.py    (per item)
#   • hooks.json                   → RENDERED (__HARNESS_TARGET__ → $CHE_REPO)
#
# Safety contract:
#   • Never deletes. Never overwrites a real (non-symlink) file silently: a real
#     target is either SKIPped (per-item collections) or backed up to .bak
#     (root pointer files, which must resolve for Trae to boot with Che rules).
#   • Rollback = remove the symlink (see adapters/trae/uninstall.sh).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHE_REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Trae agent home — canonical $HOME/.trae. Override with TRAE_HOME.
TRAE_HOME="${TRAE_HOME:-$HOME/.trae}"

COMMANDS_TARGET="$TRAE_HOME/commands"
SKILLS_TARGET="$TRAE_HOME/skills"
HOOKS_TARGET="$TRAE_HOME/hooks"

echo "Che repo     : $CHE_REPO"
echo "Trae home    : $TRAE_HOME"

# Trae IDE home is owned by the Trae IDE. If it does not exist, Trae is not
# installed here — do NOT create it (that would fake a Trae installation).
if [ ! -d "$TRAE_HOME" ]; then
  echo "SKIP: Trae home not found at $TRAE_HOME (Trae IDE not installed). Nothing to wire."
  exit 0
fi

validate_skill() {
  local skill_file="$1"

  python3 - "$skill_file" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
lines = p.read_text().splitlines()

if not lines or lines[0].strip() != "---":
    raise SystemExit(f"INVALID SKILL: {p}: missing opening YAML frontmatter")

try:
    end = next(i for i, line in enumerate(lines[1:30], start=1)
               if line.strip() == "---")
except StopIteration:
    raise SystemExit(f"INVALID SKILL: {p}: missing closing YAML frontmatter")

frontmatter = lines[1:end]

if not any(line.startswith("name:") for line in frontmatter):
    raise SystemExit(f"INVALID SKILL: {p}: missing name")

if not any(line.startswith("description:") for line in frontmatter):
    raise SystemExit(f"INVALID SKILL: {p}: missing description")
PY
}

mkdir -p "$COMMANDS_TARGET" "$SKILLS_TARGET" "$HOOKS_TARGET"

# 1. Root pointer files + rule directories.
#    These must resolve for Trae to load Che rules/domains/user overrides, so a
#    pre-existing REAL file is backed up (never lost) before the symlink lands.
link_pointer() {
  local src="$1" dst="$2" label="$3"
  if [ ! -e "$src" ]; then
    echo "SKIP: $label (source missing: $src)"
    return 0
  fi
  if [ -e "$dst" ] && [ ! -L "$dst" ]; then
    echo "WARN: $dst exists and is not a symlink. Backing up → ${dst}.bak"
    mv "$dst" "${dst}.bak"
  fi
  ln -sfn "$src" "$dst"
  echo "  → $label"
}

link_pointer "$CHE_REPO/AGENTS.md"       "$TRAE_HOME/AGENTS.md"       "AGENTS.md"
link_pointer "$CHE_REPO/CHE_RULES.md"    "$TRAE_HOME/CHE_RULES.md"    "CHE_RULES.md"
link_pointer "$CHE_REPO/CHE_COMMANDS.md" "$TRAE_HOME/CHE_COMMANDS.md" "CHE_COMMANDS.md"
link_pointer "$CHE_REPO/domains"         "$TRAE_HOME/domains"         "domains/"
link_pointer "$CHE_REPO/user_rules"      "$TRAE_HOME/user_rules"      "user_rules/"

# 2. Link Skills (per item).
INSTALLED_SKILLS=0
for skill_dir in "$CHE_REPO"/skills/*; do
  [ -d "$skill_dir" ] || continue
  [ -f "$skill_dir/SKILL.md" ] || continue

  validate_skill "$skill_dir/SKILL.md"

  skill_name="$(basename "$skill_dir")"
  target="$SKILLS_TARGET/$skill_name"

  if [ -e "$target" ] && [ ! -L "$target" ]; then
    echo "SKIP: $target exists and is not a symlink"
    continue
  fi

  ln -sfn "$skill_dir" "$target"
  INSTALLED_SKILLS=$((INSTALLED_SKILLS + 1))
done

# 3. Link Commands (per item).
INSTALLED_COMMANDS=0
for cmd_file in "$CHE_REPO"/commands/*.md; do
  [ -f "$cmd_file" ] || continue

  cmd_name="$(basename "$cmd_file")"
  target="$COMMANDS_TARGET/$cmd_name"

  if [ -e "$target" ] && [ ! -L "$target" ]; then
    echo "SKIP: $target exists and is not a symlink"
    continue
  fi

  ln -sfn "$cmd_file" "$target"
  INSTALLED_COMMANDS=$((INSTALLED_COMMANDS + 1))
done

# 4. Link Hooks (per item) + guarantee the hook scripts are executable.
#    Trae invokes hooks commands directly (see rendered hooks.json), so the
#    target scripts MUST carry the executable bit.
INSTALLED_HOOKS=0
for hook_file in "$CHE_REPO"/hooks/*.py; do
  [ -f "$hook_file" ] || continue

  hook_name="$(basename "$hook_file")"
  target="$HOOKS_TARGET/$hook_name"

  if [ -e "$target" ] && [ ! -L "$target" ]; then
    echo "SKIP: $target exists and is not a symlink"
    continue
  fi

  ln -sfn "$hook_file" "$target"
  chmod +x "$hook_file"
  INSTALLED_HOOKS=$((INSTALLED_HOOKS + 1))
done

# 5. Render hooks.json with absolute paths to THIS checkout ($CHE_REPO).
#    Source of truth = $CHE_REPO/hooks.json (contains __HARNESS_TARGET__).
HOOKS_CONFIG="$TRAE_HOME/hooks.json"
RENDERED_HOOKS="$(mktemp)"
trap 'rm -f "$RENDERED_HOOKS"' EXIT

python3 - "$CHE_REPO/hooks.json" "$RENDERED_HOOKS" "$CHE_REPO" <<'PY'
import json
from pathlib import Path
import sys

source_path, output_path, harness = map(Path, sys.argv[1:])
config = json.loads(source_path.read_text())
for event_hooks in config.get("hooks", {}).values():
    for hook in event_hooks:
        command = hook.get("command")
        if isinstance(command, str):
            hook["command"] = command.replace("__HARNESS_TARGET__", str(harness))
Path(output_path).write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
PY

if [ -f "$HOOKS_CONFIG" ] && cmp -s "$RENDERED_HOOKS" "$HOOKS_CONFIG"; then
  echo "  = hooks.json unchanged"
else
  # Never write through a symlink (would clobber the repo source file).
  [ -L "$HOOKS_CONFIG" ] && unlink "$HOOKS_CONFIG"
  if [ -f "$HOOKS_CONFIG" ]; then
    HOOKS_BKP="${HOOKS_CONFIG}.bak-$(date +%Y%m%d-%H%M%S)"
    mv "$HOOKS_CONFIG" "$HOOKS_BKP"
    echo "  ~ hooks.json (previous → $HOOKS_BKP)"
  fi
  cp "$RENDERED_HOOKS" "$HOOKS_CONFIG"
  echo "  + hooks.json rendered"
fi

echo
echo "Che — Trae adapter installed successfully!"
echo "Injection points now live under $TRAE_HOME (symlinks only):"
echo "  • AGENTS.md / CHE_RULES.md / CHE_COMMANDS.md"
echo "  • domains/  user_rules/            (dir symlinks)"
echo "  • skills/   : $INSTALLED_SKILLS"
echo "  • commands/ : $INSTALLED_COMMANDS"
echo "  • hooks/    : $INSTALLED_HOOKS  (+ hooks.json)"
echo
echo "For this Che checkout in shell:"
echo "  export CHE_HOME=\"$CHE_REPO\""
