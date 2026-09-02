#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

FAKE_BIN="$TEST_ROOT/bin"
mkdir -p "$FAKE_BIN"
printf '#!/usr/bin/env bash\nexit 0\n' > "$FAKE_BIN/corepack"
chmod +x "$FAKE_BIN/corepack"

install_target() {
  local target="$1"
  (cd "$TEST_ROOT" && PATH="$FAKE_BIN:$PATH" bash "$REPO_ROOT/scripts/install-harness.sh" \
    --source "$REPO_ROOT" --target "$target" --apply >/dev/null)
  python3 - "$target/hooks.json" "$target" <<'PY'
import json
from pathlib import Path
import sys

config_path, target = sys.argv[1:]
config = json.loads(Path(config_path).read_text())
commands = [hook["command"] for hooks in config["hooks"].values() for hook in hooks]
expected = {
    f"{target}/hooks/pretooluse-worktree-binding.sh",
    f"{target}/hooks/posttooluse-3layer-dedup.sh",
    f"{target}/hooks/posttooluse-lang-pt-check.sh",
}
assert set(commands) == expected
assert "/home/laion" not in Path(config_path).read_text()
PY
  test -x "$target/scripts/install-harness.sh"
  for hook in "$target"/hooks/*.sh; do
    test -x "$hook"
    bash -n "$hook"
  done
}

TARGET_A="$TEST_ROOT/harness-trae-a"
TARGET_B="$TEST_ROOT/harness-trae-b"
install_target "$TARGET_A"
install_target "$TARGET_B"
! rg -q "$TARGET_A" "$TARGET_B/hooks.json"
! rg -q "$TARGET_B" "$TARGET_A/hooks.json"

mkdir -p "$TARGET_A/bindings" "$TEST_ROOT/Lumos.worktrees/feature-a" "$TEST_ROOT/Lumos.worktrees/feature-b"
cat > "$TARGET_A/bindings/registry.jsonl" <<EOF
{"session_id":"trae-event","status":"BOUND","worktree_root":"$TEST_ROOT/Lumos.worktrees/feature-a","flags":{"LANG_DOCS":"pt-BR"}}
{"session_id":"inherited-codex","status":"BOUND","worktree_root":"$TEST_ROOT/Lumos.worktrees/feature-b","flags":{"LANG_DOCS":"en"}}
{"session_id":"legacy-trae","status":"BOUND","worktree_root":"$TEST_ROOT/Lumos.worktrees/feature-a","flags":{"LANG_PT_CHECK":"DISABLED"}}
EOF

PRE_HOOK="$TARGET_A/hooks/pretooluse-worktree-binding.sh"
ALLOW_PAYLOAD=$(printf '{"event":"PreToolUse","sessionId":"trae-event","toolName":"Read","toolArgs":{"file_path":"%s/file.ts"}}' "$TEST_ROOT/Lumos.worktrees/feature-a")
ALLOW_OUTPUT=$(HARNESS_HOME="$TARGET_A" HARNESS_SESSION_ID="inherited-codex" "$PRE_HOOK" <<<"$ALLOW_PAYLOAD")
test "$(jq -r .decision <<<"$ALLOW_OUTPUT")" = "allow"

BLOCK_PAYLOAD=$(printf '{"event":"PreToolUse","sessionId":"trae-event","toolName":"Read","toolArgs":{"file_path":"%s/file.ts"}}' "$TEST_ROOT/Lumos.worktrees/feature-b")
set +e
BLOCK_OUTPUT=$(HARNESS_HOME="$TARGET_A" HARNESS_SESSION_ID="inherited-codex" "$PRE_HOOK" <<<"$BLOCK_PAYLOAD")
BLOCK_EXIT=$?
set -e
test "$BLOCK_EXIT" -eq 2
test "$(jq -r .decision <<<"$BLOCK_OUTPUT")" = "block"

mkdir -p "$TARGET_A/skills/portability-test"
cat > "$TARGET_A/skills/portability-test/SKILL.md" <<'EOF'
portable duplicate line one
portable duplicate line two
portable duplicate line three
portable duplicate line four
EOF
cat > "$TARGET_A/HARNESS_RULES.md" <<'EOF'
portable duplicate line one
portable duplicate line two
portable duplicate line three
portable duplicate line four
EOF
DEDUP_PAYLOAD=$(printf '{"event":"PostToolUse","sessionId":"trae-event","toolName":"Write","toolArgs":{"file_path":"%s/HARNESS_RULES.md"}}' "$TARGET_A")
DEDUP_OUTPUT=$(HARNESS_HOME="$TARGET_A" "$TARGET_A/hooks/posttooluse-3layer-dedup.sh" <<<"$DEDUP_PAYLOAD")
test "$(jq -r .decision <<<"$DEDUP_OUTPUT")" = "allow"
test "$(jq -r '.additionalContext | length > 0' <<<"$DEDUP_OUTPUT")" = "true"

LANG_HOOK="$TARGET_A/hooks/posttooluse-lang-pt-check.sh"
LANG_PAYLOAD=$(printf '{"event":"PostToolUse","sessionId":"trae-event","toolName":"Write","toolArgs":{"file_path":"%s/HARNESS_RULES.md"}}' "$TARGET_A")
LANG_OUTPUT=$(HARNESS_HOME="$TARGET_A" HARNESS_SESSION_ID="inherited-codex" "$LANG_HOOK" <<<"$LANG_PAYLOAD")
test "$(jq -r .decision <<<"$LANG_OUTPUT")" = "allow"
rg -q 'LANG_DOCS=pt-BR' <<<"$(jq -r .reason <<<"$LANG_OUTPUT")"

LEGACY_PAYLOAD=$(printf '{"event":"PostToolUse","sessionId":"legacy-trae","toolName":"Write","toolArgs":{"file_path":"%s/HARNESS_RULES.md"}}' "$TARGET_A")
LEGACY_OUTPUT=$(HARNESS_HOME="$TARGET_A" "$LANG_HOOK" <<<"$LEGACY_PAYLOAD")
test "$(jq -r .decision <<<"$LEGACY_OUTPUT")" = "allow"
rg -q 'LANG_DOCS=pt-BR' <<<"$(jq -r .reason <<<"$LEGACY_OUTPUT")"

! rg -n 'hooks|hooks.json' "$REPO_ROOT/adapters/codex/install.sh"
! find "$HOME/.agents/skills" -maxdepth 1 -type l -lname '*hooks*' -print -quit 2>/dev/null | rg -q .

printf '%s\n' "hooks portability smoke: PASS"
