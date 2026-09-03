#!/usr/bin/env python3
import sys
import json
import os

# Ensure che_core is in the python path
che_home = os.environ.get("CHE_HOME") or os.environ.get("HARNESS_HOME") or os.path.expanduser("~/.trae")
if che_home not in sys.path:
    sys.path.insert(0, che_home)

from che_core.hooks import posttooluse_3layer_dedup

def main():
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            print(json.dumps({"decision": "allow"}))
            return
            
        input_json = json.loads(input_data)
        result = posttooluse_3layer_dedup(input_json)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"decision": "allow", "additionalContext": f"Hook error: {e}"}))

if __name__ == "__main__":
    main()
