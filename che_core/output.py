"""One payload, one shape — the single place that decides how a success is rendered.

A Che command's success output serves two callers who want opposite things. A human, or a skill
doing `eval "$(che …)"`, reads `export K="v"` lines; an agent reads a JSON object. Both are the
same mapping, so the choice is made here rather than at every call site — the dialects did not
drift because anyone chose them, they drifted because each command decided locally.

`as_json` is the caller's answer to one question: did the caller ask for machine-readable output?
It is the global `--json` or the command's own flag (see `cli._wants_json`). It is never inferred
from whether stdout is a tty: Che is called from hooks and skills, where a tty is meaningless, so
inferring would make the shape depend on where the command was invoked from.
"""

import json
from typing import Any, Mapping


def print_json(payload: Any) -> None:
    """Print one JSON value to stdout, indented for a human who has to read it in a terminal."""
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def emit_mapping(payload: Mapping[str, Any], *, as_json: bool, shell: bool = False) -> None:
    """Render a flat mapping as JSON, as `export K="v"` (shell) or as `K=v` (kv).

    PRE: payload keys are strings.
    POST: exactly one shape is written; `as_json` wins when both could apply.
    """
    if as_json:
        print_json(payload)
        return
    for key, value in payload.items():
        print(f'export {key}="{value}"' if shell else f"{key}={value}")
