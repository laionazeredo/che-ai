#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

HARNESS_FIXTURE="$TEST_ROOT/harness"
MAIN_REPO="$TEST_ROOT/project-alpha"
BOUND_WORKTREE="$TEST_ROOT/project-alpha-wt-feature"
OTHER_REPO="$TEST_ROOT/project-beta"
SESSIONS_ROOT="$TEST_ROOT/harness-sessions"
EXTERNAL_PATH="$TEST_ROOT/non-project/cache.txt"

mkdir -p "$HARNESS_FIXTURE/hooks" "$HARNESS_FIXTURE/contracts" "$HARNESS_FIXTURE/bindings" \
  "$SESSIONS_ROOT/workspace/project/sessions/trae-event" "$(dirname "$EXTERNAL_PATH")"
cp "$REPO_ROOT/hooks/pretooluse-worktree-binding.sh" "$HARNESS_FIXTURE/hooks/"
cp "$REPO_ROOT/contracts/harness_sessions_contract.sh" "$HARNESS_FIXTURE/contracts/"

git init -q "$MAIN_REPO"
git -C "$MAIN_REPO" config user.email hooks@example.test
git -C "$MAIN_REPO" config user.name "Hooks Test"
touch "$MAIN_REPO/tracked.txt"
git -C "$MAIN_REPO" add tracked.txt
git -C "$MAIN_REPO" commit -qm initial
git -C "$MAIN_REPO" worktree add -qb feature "$BOUND_WORKTREE"
git init -q "$OTHER_REPO"
touch "$EXTERNAL_PATH"

cat > "$HARNESS_FIXTURE/bindings/registry.jsonl" <<EOF
{"session_id":"trae-event","status":"BOUND","worktree_root":"$BOUND_WORKTREE"}
{"session_id":"inherited-codex","status":"BOUND","worktree_root":"$OTHER_REPO"}
EOF

HOOK="$HARNESS_FIXTURE/hooks/pretooluse-worktree-binding.sh"
ARTIFACT_PATH="$SESSIONS_ROOT/workspace/project/sessions/trae-event/report.md"

run_hook() {
  local payload="$1"
  local output_file="$TEST_ROOT/output.json"
  set +e
  HARNESS_HOME="$HARNESS_FIXTURE" HARNESS_SESSIONS_ROOT="$SESSIONS_ROOT" \
    HARNESS_SESSION_ID="inherited-codex" bash "$HOOK" <<<"$payload" >"$output_file"
  HOOK_EXIT=$?
  set -e
  jq -e . "$output_file" >/dev/null
  HOOK_DECISION="$(jq -r .decision "$output_file")"
}

expect_decision() {
  local expected_decision="$1"
  local expected_exit="$2"
  test "$HOOK_DECISION" = "$expected_decision"
  test "$HOOK_EXIT" -eq "$expected_exit"
}

run_hook "$(printf '{"sessionId":"trae-event","toolName":"Read","toolArgs":{"file_path":"%s/src/new.ts"}}' "$BOUND_WORKTREE")"
expect_decision allow 0

run_hook "$(printf '{"sessionId":"trae-event","toolName":"Read","toolArgs":{"path":"%s/file.ts"}}' "$OTHER_REPO")"
expect_decision block 2

run_hook "$(printf '{"sessionId":"trae-event","toolName":"RunCommand","toolArgs":{"cwd":"%s"}}' "$MAIN_REPO")"
expect_decision block 2

run_hook "$(printf '{"sessionId":"trae-event","toolName":"Write","toolArgs":{"file_path":"%s"}}' "$ARTIFACT_PATH")"
expect_decision allow 0

run_hook "$(printf '{"sessionId":"trae-event","toolName":"Write","toolArgs":{"file_paths":["%s","%s/file.ts"]}}' "$ARTIFACT_PATH" "$OTHER_REPO")"
expect_decision block 2

run_hook "$(printf '{"sessionId":"trae-event","toolName":"Grep","toolArgs":{"target_directories":["%s/src","%s/tests"]}}' "$BOUND_WORKTREE" "$BOUND_WORKTREE")"
expect_decision allow 0

run_hook "$(printf '{"sessionId":"trae-event","toolName":"Grep","toolArgs":{"file_paths":["%s/src/file.ts","%s"]}}' "$BOUND_WORKTREE" "$EXTERNAL_PATH")"
expect_decision allow 0

run_hook "$(printf '{"sessionId":"unbound-trae","toolName":"Read","toolArgs":{"file_path":"%s/file.ts"}}' "$OTHER_REPO")"
expect_decision allow 0

run_hook "$(printf '{"sessionId":"trae-event","toolName":"Read","toolArgs":{"ignore":["%s/generated"],"file_path":"%s/src/file.ts"}}' "$BOUND_WORKTREE" "$BOUND_WORKTREE")"
expect_decision allow 0

! grep -En 'Lumos|Lumos\.worktrees' "$REPO_ROOT/hooks/pretooluse-worktree-binding.sh"
printf '%s\n' "generic worktree binding smoke: PASS"
