#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHE_REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Official Claude Code user config home env var (docs: code.claude.com/docs/en/settings §Advanced)
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
# User-scope injection points (official: code.claude.com/docs/en/memory, /skills, /hooks)
SKILLS_TARGET="$CLAUDE_CONFIG_DIR/skills"
COMMANDS_TARGET="$CLAUDE_CONFIG_DIR/commands"
RULES_TARGET="$CLAUDE_CONFIG_DIR/rules"

echo "Che repo              : $CHE_REPO"
echo "Claude Code config dir: $CLAUDE_CONFIG_DIR (override via env CLAUDE_CONFIG_DIR)"
echo "Skills target         : $SKILLS_TARGET"
echo "Commands target       : $COMMANDS_TARGET"
echo "User rules target     : $RULES_TARGET"

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

mkdir -p "$CLAUDE_CONFIG_DIR"
mkdir -p "$SKILLS_TARGET"
mkdir -p "$COMMANDS_TARGET"
# User-scope rules folder (official: docs/en/memory §User-level rules, recursively loaded)
mkdir -p "$RULES_TARGET/che-domains"
mkdir -p "$RULES_TARGET/che-user"

# 1. Link CLAUDE.md (user-scope adapter, canonical location ~/.claude/CLAUDE.md)
AGENTS_TARGET="$CLAUDE_CONFIG_DIR/CLAUDE.md"
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

# 4. Setup Hooks in settings.json (NON-DESTRUCTIVE DEEP MERGE)
# Official hooks doc: code.claude.com/docs/en/hooks — settings precedence: Managed → User → Project
# Strategy: preserve EVERY existing user setting (theme, plugins, their OWN hooks).
#   For each Che hook event list: append-only, skip duplicates, never overwrite user hooks.
python3 - "$CHE_REPO" "$CLAUDE_CONFIG_DIR" <<'PY'
import json
import sys
from pathlib import Path

che_repo = sys.argv[1]
claude_config_dir = Path(sys.argv[2])
settings_path = claude_config_dir / "settings.json"

# Che hooks we want to ENSURE are present (append if missing, never duplicate)
che_hooks = {
    "PreToolUse": [
        {"command": f"python3 {che_repo}/hooks/pretooluse-worktree-binding.py"},
    ],
    "PostToolUse": [
        {"command": f"python3 {che_repo}/hooks/posttooluse-3layer-dedup.py"},
        {"command": f"python3 {che_repo}/hooks/posttooluse-lang-pt-check.py"},
    ],
}

# Step 1: Load existing settings intact — never wipe theme/plugins/user hooks
settings = {}
if settings_path.exists():
    try:
        with open(settings_path, "r") as f:
            settings = json.load(f)
    except Exception:
        # Corrupt file: start fresh but this is rare user-visible corner case
        settings = {}

# Step 2: Ensure settings["hooks"] dict exists without clobbering existing hooks dict
if "hooks" not in settings or not isinstance(settings["hooks"], dict):
    settings["hooks"] = {}

# Step 3: For each event, APPEND Che hooks to user's existing list, dedup by command string
for event, che_entries in che_hooks.items():
    # Ensure event list exists
    if event not in settings["hooks"] or not isinstance(settings["hooks"][event], list):
        settings["hooks"][event] = []
    existing_commands = {
        entry.get("command") for entry in settings["hooks"][event]
        if isinstance(entry, dict) and "command" in entry
    }
    for che_entry in che_entries:
        if che_entry["command"] not in existing_commands:
            settings["hooks"][event].append(che_entry)

# Step 4: Write back (preserves all other keys the user had set)
with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
PY

# 4b. Inject user-scope rules via symlinks (official: code.claude.com/docs/en/memory)
# Che domain rulebooks → ~/.claude/rules/che-domains/ (loaded for all projects, path-scopable via frontmatter)
INSTALLED_DOMAIN_RULES=0
for domain_dir in "$CHE_REPO"/domains/*; do
  [ -d "$domain_dir" ] || continue
  domain_name="$(basename "$domain_dir")"
  # Rulebook priority: rulebook.md → SKILL.md → index.md → first *.md alphabetically
  rulebook=""
  for candidate in "rulebook.md" "SKILL.md" "index.md"; do
    if [ -f "$domain_dir/$candidate" ]; then
      rulebook="$domain_dir/$candidate"
      break
    fi
  done
  if [ -z "$rulebook" ]; then
    # Fallback: first .md file in domain dir
    first_md="$(find "$domain_dir" -maxdepth 1 -type f -name "*.md" 2>/dev/null | head -n 1)"
    [ -n "$first_md" ] && rulebook="$first_md"
  fi
  [ -z "$rulebook" ] && continue

  target="$RULES_TARGET/che-domains/${domain_name}.md"
  if [ -e "$target" ] && [ ! -L "$target" ]; then
    echo "SKIP: $target exists and is not a symlink"
    continue
  fi
  ln -sfn "$rulebook" "$target"
  INSTALLED_DOMAIN_RULES=$((INSTALLED_DOMAIN_RULES + 1))
done

# Che user overrides → ~/.claude/rules/che-user/ (loaded for all projects, take precedence)
INSTALLED_USER_RULES=0
for rule_file in "$CHE_REPO"/user_rules/*.md; do
  [ -f "$rule_file" ] || continue
  rule_name="$(basename "$rule_file")"
  [ "$rule_name" = ".gitkeep" ] && continue

  target="$RULES_TARGET/che-user/$rule_name"
  if [ -e "$target" ] && [ ! -L "$target" ]; then
    echo "SKIP: $target exists and is not a symlink"
    continue
  fi
  ln -sfn "$rule_file" "$target"
  INSTALLED_USER_RULES=$((INSTALLED_USER_RULES + 1))
done

echo
echo "Che — Claude Code adapter installed successfully!"
echo
echo "Linked artifacts:"
echo "  • User CLAUDE.md   : $CLAUDE_CONFIG_DIR/CLAUDE.md"
echo "  • Skills           : $INSTALLED_SKILLS (source-of-truth: $CHE_REPO/skills/)"
echo "  • Commands (legacy): $INSTALLED_COMMANDS"
echo "  • Domain rules     : $INSTALLED_DOMAIN_RULES → $RULES_TARGET/che-domains/"
echo "  • User scope rules : $INSTALLED_USER_RULES → $RULES_TARGET/che-user/"
echo "  • Hooks            : non-destructive deep-merge into $CLAUDE_CONFIG_DIR/settings.json"
echo
echo "Env var override for custom Claude Code home (official docs):"
echo "  export CLAUDE_CONFIG_DIR=\"<path>\"  (default: \$HOME/.claude)"
echo
echo "For this Che checkout in shell:"
echo "  export CHE_HOME=\"$CHE_REPO\""
