#!/usr/bin/env bash
# Hook 2 (GLOBAL OBRIGATÓRIO): PostToolUse — 3-Layer Non-Duplication Guard
# This hook uses the new Python core.

set -euo pipefail

INPUT_JSON="$(cat)"
CHE_HOME="${CHE_HOME:-${HARNESS_HOME:-$HOME/.trae}}"

python3 -c "
import sys, json
sys.path.insert(0, '$CHE_HOME')
from che_core.hooks import posttooluse_3layer_dedup

input_json = json.loads(sys.argv[1])
result = posttooluse_3layer_dedup(input_json)
print(json.dumps(result))
" "$INPUT_JSON"
