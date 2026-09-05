#!/usr/bin/env python3
import json
import os
import sys

che_home = os.environ.get("CHE_HOME") or os.environ.get("HARNESS_HOME") or os.path.expanduser("~/.trae")
if che_home not in sys.path:
    sys.path.insert(0, che_home)

from che_core.hooks import posttooluse_git_worktree  # noqa: E402 (sys.path inserido logo acima é intencional)


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
        print(json.dumps({"decision": "allow", "additionalContext": f"Hook git-worktree error (safe-noop): {e}"}))


if __name__ == "__main__":
    main()
