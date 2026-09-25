#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

# Ensure che_core is in the python path.
# Use the canonical CHE_HOME resolution cascade (env → ~/.che-ai → legacy ~/.trae).
# Do this BEFORE importing anything from che_core so the helper itself lives in che_core.
_che_home_candidate = os.environ.get("CHE_HOME") or os.environ.get("HARNESS_HOME")
if _che_home_candidate:
    _che_home = Path(_che_home_candidate).expanduser().resolve()
else:
    _home = Path(os.path.expanduser("~"))
    _new_default = _home / ".che-ai"
    _legacy = _home / ".trae"
    if _new_default.exists():
        _che_home = _new_default
    elif _legacy.exists() and (_legacy / "CHE_RULES.md").is_file():
        _che_home = _legacy
    else:
        _che_home = _new_default
che_home = str(_che_home)
if che_home not in sys.path:
    sys.path.insert(0, che_home)

# ruff: noqa: E402
from che_core.hooks import pretooluse_worktree_binding


def main():
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            print(json.dumps({"decision": "allow", "reason": "Empty input"}))
            return

        input_json = json.loads(input_data)
        result = pretooluse_worktree_binding(input_json)
        print(json.dumps(result))
    except Exception as e:
        # Fallback to allow if hook crashes, to avoid breaking IDE
        print(json.dumps({"decision": "allow", "reason": f"Hook error: {e}"}))


if __name__ == "__main__":
    main()
