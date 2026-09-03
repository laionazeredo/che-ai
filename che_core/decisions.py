import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from che_core.paths import resolve_workspace_name, resolve_worktree_slug, get_workspaces_root

def get_decisions_path(worktree_root: str, cwd_override: Optional[str] = None) -> Path:
    if not worktree_root:
        print("get_decisions_path: worktree_root empty", file=sys.stderr)
        sys.exit(2)
        
    hwn = resolve_workspace_name(cwd_override)
    sl = resolve_worktree_slug(worktree_root)
    workspaces_root = get_workspaces_root()
    
    out_path = workspaces_root / hwn / sl / ".wt" / "decisions.log.jsonl"
    return out_path

def append_decision_jsonl(
    worktree_root: str, 
    event_type: str, 
    payload_s: str = "{}", 
    ts_override: Optional[str] = None,
    session_id: Optional[str] = None,
    spec_id: Optional[str] = None
):
    if not worktree_root or not event_type:
        print("append_decision_jsonl: worktree_root and event_type are required.", file=sys.stderr)
        sys.exit(2)
        
    out_path = get_decisions_path(worktree_root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
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
        "_v": 1
    }
    
    line = json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    
    if out_path.exists():
        with open(out_path, "rb") as f:
            existing = f.read()
        if (line + "\n").encode() in existing:
            return

    with open(out_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
