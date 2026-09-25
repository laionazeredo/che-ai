import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from che_core.diagnostics import fail
from che_core.paths import compute_paths
from che_core.project_layout import append_line_atomic


def get_decisions_path(worktree_root: str, cwd_override: Optional[str] = None) -> Path:
    """Resolve ``decisions.log.jsonl`` for a bound worktree.

    Delegates to :func:`che_core.paths.compute_paths` so the decisions log lives in
    exactly the same tree as every other artifact of that worktree.

    Historically this module carried its own duplicate formula
    (``<root>/<workspace>/<worktree-slug>/.wt/``) that resolved the workspace from
    ``os.getcwd()``. The two formulas disagreed, so a worktree's decision history
    and its artifacts silently landed in different trees — the memory of a project
    never met itself.
    """
    if not worktree_root:
        fail("MISSING_WORKTREE_ROOT")

    paths = compute_paths(worktree_root, "decisions", cwd_override)
    return Path(paths["CHE_DECISIONS_PATH"])


def append_decision_jsonl(
    worktree_root: str,
    event_type: str,
    payload_s: str = "{}",
    ts_override: Optional[str] = None,
    session_id: Optional[str] = None,
    spec_id: Optional[str] = None,
) -> None:
    """Append one decision record to the worktree's ``decisions.log.jsonl``.

    Preconditions: ``worktree_root`` is bound and ``event_type`` is non-empty.
    Postcondition: the log grows by at most one complete, parseable JSONL line
    (duplicate suppression is best-effort and never rewrites existing content).
    """
    if not worktree_root:
        fail("MISSING_WORKTREE_ROOT")
    if not event_type:
        fail("MISSING_EVENT_TYPE")

    out_path = get_decisions_path(worktree_root)

    ts = ts_override or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def parse_nullable(s):
        if s in ("null", "None", "", "NONE", None):
            return None
        return s

    try:
        payload = json.loads(payload_s)
        if not isinstance(payload, dict):
            payload = {"value": payload}
    except Exception:
        payload = {"raw": payload_s}

    entry = {
        "ts": ts,
        "event": event_type,
        "spec_id": parse_nullable(spec_id),
        "session_id": parse_nullable(session_id),
        "worktree_root": worktree_root,
        "data": payload,
        "_v": 1,
    }

    line = json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    # Best-effort duplicate suppression. This read is not transactional (two
    # writers can both miss and both append); a duplicate line is harmless because
    # the log is append-only and every consumer tolerates repeats.
    if out_path.exists():
        try:
            existing = out_path.read_bytes()
        except OSError:
            existing = b""
        if (line + "\n").encode() in existing:
            return

    try:
        append_line_atomic(out_path, line)
    except ValueError as exc:
        fail("APPEND_FAILED", target=str(out_path), detail=str(exc))
