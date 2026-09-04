#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHE_REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
AGENTS_HOME="${AGENTS_HOME:-$HOME/.agents}"
SKILLS_TARGET="$AGENTS_HOME/skills"
COMMANDS_TARGET="$CODEX_HOME/commands"

echo "Che repo      : $CHE_REPO"
echo "Codex home    : $CODEX_HOME"
echo "Agents home   : $AGENTS_HOME"
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

mkdir -p "$CODEX_HOME"
mkdir -p "$SKILLS_TARGET"
mkdir -p "$COMMANDS_TARGET"

# 1. Link AGENTS.md
AGENTS_TARGET="$CODEX_HOME/AGENTS.md"
AGENTS_SOURCE="$SCRIPT_DIR/AGENTS.md"

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

# 4. Setup Hooks
HOOKS_CONFIG="$CODEX_HOME/hooks.json"
cat <<EOF > "$HOOKS_CONFIG"
{
  "hooks": {
    "PreToolUse": [
      {
        "type": "command",
        "command": "python3 $CHE_REPO/hooks/pretooluse-worktree-binding.py",
        "statusMessage": "Verifying worktree binding..."
      }
    ],
    "PostToolUse": [
      {
        "type": "command",
        "command": "python3 $CHE_REPO/hooks/posttooluse-3layer-dedup.py",
        "statusMessage": "Deduplicating rules..."
      },
      {
        "type": "command",
        "command": "python3 $CHE_REPO/hooks/posttooluse-lang-pt-check.py",
        "statusMessage": "Checking language consistency..."
      }
    ]
  }
}
EOF

# 5. Enable hooks in config.toml if not already enabled
CONFIG_TOML="$CODEX_HOME/config.toml"
if [ -f "$CONFIG_TOML" ]; then
  if ! grep -q "hooks = true" "$CONFIG_TOML"; then
    echo -e "\n[features]\nhooks = true" >> "$CONFIG_TOML"
  fi
else
  cat <<EOF > "$CONFIG_TOML"
[features]
hooks = true

[shell_environment_policy]
inherit = "all"
EOF
fi

echo
echo "Codex Che adapter installed successfully!"
echo "Skills linked   : $INSTALLED_SKILLS"
echo "Commands linked : $INSTALLED_COMMANDS"
echo "Hooks configured: $HOOKS_CONFIG"
echo
echo "For this checkout use:"
echo "  export CHE_HOME=\"$CHE_REPO\""
