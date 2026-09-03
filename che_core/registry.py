import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from che_core.paths import get_che_home, get_workspaces_root, resolve_workspace_name, resolve_worktree_slug

def get_registry_path() -> Path:
    che_home = get_che_home()
    return che_home / "bindings" / "registry.jsonl"

def _clean_payload(payload_s: str) -> Dict[str, Any]:
    try:
        payload = json.loads(payload_s)
        if not isinstance(payload, dict):
            payload = {"value": payload}
    except Exception:
        payload = {"raw": payload_s}
    return payload

def registry_append_jsonl(session_id: str, status: str, worktree_root: str, payload_s: str = "{}", ts_override: Optional[str] = None):
    if not session_id or not status or not worktree_root:
        print("registry_append_jsonl: session_id, status, and worktree_root are required.", file=sys.stderr)
        sys.exit(2)
        
    payload = _clean_payload(payload_s)
    
    if status == "BOUND":
        # Simulate legacy artifact cleanup if needed
        # In python, we can just ensure directories exist for now. The heavy lifting is done by tools.
        pass

    out_path = get_registry_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    ts = ts_override or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Process flags based on bash logic
    legacy_pt_check = payload.pop("LANG_PT_CHECK", None)
    incoming_flags = payload.pop("flags", {}) or {}
    
    if legacy_pt_check is None:
        legacy_pt_check = incoming_flags.pop("LANG_PT_CHECK", None)
        
    flags = {
        "LANG_CODE": incoming_flags.pop("LANG_CODE", "en"),
        "LANG_DOCS": incoming_flags.pop("LANG_DOCS", "pt-BR" if legacy_pt_check == "DISABLED" else "en"),
        "LANG_CHAT": incoming_flags.pop("LANG_CHAT", "pt-BR"),
        "LANG_REPORT": incoming_flags.pop("LANG_REPORT", "en"),
    }
    
    for k, v in incoming_flags.items():
        if k not in flags:
            flags[k] = v
            
    if legacy_pt_check is not None:
        flags["LANG_PT_CHECK"] = legacy_pt_check
        
    event = payload.pop("event", None)
    if not event:
        if status == "FLAGS":
            event = "BIND_FLAGS_UPDATE"
        elif status == "UNBOUND":
            event = "BIND_UNBOUND"
        else:
            event = "BIND_APPEND"
            
    entry = {
        "ts": ts,
        "event": event,
        "session_id": session_id,
        "status": status,
        "worktree_root": worktree_root,
        "workspace_name": payload.pop("workspace_name", None),
        "worktree_slug": payload.pop("worktree_slug", None),
        "branch": payload.pop("branch", None),
        "friendly_name": payload.pop("friendly_name", None),
        "che_session_dir": payload.pop("che_session_dir", payload.pop("harness_session_dir", None)),
        "che_workspace_shared": payload.pop("che_workspace_shared", payload.pop("harness_workspace_shared", None)),
        "workspace_file": payload.pop("workspace_file", None),
        "reason": payload.pop("reason", None),
        "flags": flags,
        "data": payload,
        "_v": 2
    }
    
    line = json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    
    # Avoid duplicate lines
    if out_path.exists():
        with open(out_path, "rb") as f:
            existing = f.read()
        if (line + "\n").encode() in existing:
            return

    with open(out_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def registry_lookup_last(session_id: str) -> Optional[Dict[str, Any]]:
    out_path = get_registry_path()
    if not out_path.exists():
        return None
        
    last = None
    with open(out_path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                e = json.loads(ln)
                if e.get("session_id") == session_id:
                    last = e
            except Exception:
                continue
                
    return last
