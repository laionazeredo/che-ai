#!/usr/bin/env bash
# Hook 3 (GLOBAL WARN-only): PostToolUse — Portuguese Text Detector in written code/content
# This hook uses the new Python core.

set -euo pipefail

INPUT_JSON="$(cat)"
CHE_HOME="${CHE_HOME:-${HARNESS_HOME:-$HOME/.trae}}"

python3 -c "
import sys, json
sys.path.insert(0, '$CHE_HOME')
from che_core.hooks import posttooluse_lang_pt_check

input_json = json.loads(sys.argv[1])
result = posttooluse_lang_pt_check(input_json)
print(json.dumps(result))
" "$INPUT_JSON"
