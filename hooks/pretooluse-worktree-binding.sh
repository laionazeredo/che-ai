#!/usr/bin/env bash
# Hook 1 (GLOBAL OBRIGATÓRIO §19): PreToolUse — Worktree Session Binding Guard
# This hook uses the new Python core to validate paths.

set -euo pipefail

INPUT_JSON="$(cat)"
CHE_HOME="${CHE_HOME:-${HARNESS_HOME:-$HOME/.trae}}"

python3 -c "
import sys, json
sys.path.insert(0, '$CHE_HOME')
from che_core.hooks import pretooluse_worktree_binding

input_json = json.loads(sys.argv[1])
result = pretooluse_worktree_binding(input_json)
print(json.dumps(result))
" "$INPUT_JSON"
