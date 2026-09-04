#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHE_REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"

CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
SKILLS_TARGET="$CLAUDE_HOME/skills"
COMMANDS_TARGET="$CLAUDE_HOME/commands"

echo "Che repo      : $CHE_REPO"
echo "Claude home   : $CLAUDE_HOME"
echo "Skills target : $SKILLS_TARGET"
echo "Commands target: $COMMANDS_TARGET"

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

mkdir -p "$CLAUDE_HOME"
mkdir -p "$SKILLS_TARGET"
mkdir -p "$COMMANDS_TARGET"

# 1. Link CLAUDE.md
AGENTS_TARGET="$CLAUDE_HOME/CLAUDE.md"
AGENTS_SOURCE="$SCRIPT_DIR/CLAUDE.md"

if [ -e "$AGENTS_TARGET" ] && [ ! -L "$AGENTS_TARGET" ]; then
  echo "WARN: $AGENTS_TARGET already exists and is not a symlink. Backing up..."
  mv "$AGENTS_TARGET" "${AGENTS_TARGET}.bak"
fi
ln -sfn "$AGENTS_SOURCE" "$AGENTS_TARGET"

# 2. Link Skills
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

# 3. Link Commands
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

# 4. Setup Hooks in settings.json
# Note: Claude Code uses settings.json for hooks. 
# This script uses python to merge the hooks configuration into existing settings.json.
python3 - "$CHE_REPO" "$CLAUDE_HOME" <<'PY'
import json
import sys
from pathlib import Path

che_repo = sys.argv[1]
claude_home = Path(sys.argv[2])
settings_path = claude_home / "settings.json"

new_hooks = {
    "PreToolUse": [
        {
            "command": f"python3 {che_repo}/hooks/pretooluse-worktree-binding.py"
        }
    ],
    "PostToolUse": [
        {
            "command": f"python3 {che_repo}/hooks/posttooluse-3layer-dedup.py"
        },
        {
            "command": f"python3 {che_repo}/hooks/posttooluse-lang-pt-check.py"
        }
    ]
}

settings = {}
if settings_path.exists():
    try:
        with open(settings_path, "r") as f:
            settings = json.load(f)
    except Exception:
        pass

settings["hooks"] = new_hooks

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
PY

echo
echo "Claude Code Che adapter installed successfully!"
echo "Skills linked   : $INSTALLED_SKILLS"
echo "Commands linked : $INSTALLED_COMMANDS"
echo "Hooks configured in: $CLAUDE_HOME/settings.json"
echo
echo "For this checkout use:"
echo "  export CHE_HOME=\"$CHE_REPO\""
