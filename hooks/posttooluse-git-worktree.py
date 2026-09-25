#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

# Canonical CHE_HOME resolution cascade: env → ~/.che-ai (new default) → legacy ~/.trae if valid checkout
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

from che_core.hooks import posttooluse_git_worktree  # noqa: E402 (sys.path inserted above is intentional)


def main():
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            print(json.dumps({"decision": "allow"}))
            return
        input_json = json.loads(input_data)
        result = posttooluse_git_worktree(input_json)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"decision": "allow", "additionalContext": f"git-worktree hook error (safe-noop): {e}"}))


if __name__ == "__main__":
    main()
