#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS_REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
AGENTS_HOME="${AGENTS_HOME:-$HOME/.agents}"
SKILLS_TARGET="$AGENTS_HOME/skills"

echo "Harness repo : $HARNESS_REPO"
echo "Codex home   : $CODEX_HOME"
echo "Agents home  : $AGENTS_HOME"

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

mkdir -p "$CODEX_HOME"
mkdir -p "$SKILLS_TARGET"

AGENTS_TARGET="$CODEX_HOME/AGENTS.md"
AGENTS_SOURCE="$SCRIPT_DIR/AGENTS.md"

if [ -e "$AGENTS_TARGET" ] && [ ! -L "$AGENTS_TARGET" ]; then
  echo "ABORT: $AGENTS_TARGET already exists and is not a symlink."
  echo "Preserving existing Codex configuration."
  exit 2
fi

ln -sfn "$AGENTS_SOURCE" "$AGENTS_TARGET"

INSTALLED=0

for skill_dir in "$HARNESS_REPO"/skills/*; do
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
  INSTALLED=$((INSTALLED + 1))
done

echo
echo "Codex Harness adapter installed."
echo "Skills linked : $INSTALLED"
echo
echo "For this checkout use:"
echo "  export HARNESS_HOME=\"$HARNESS_REPO\""
