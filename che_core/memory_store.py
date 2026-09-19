"""Pluggable decision/memory backend for Che.

Normal (IDE) environment: decisions append to ``decisions.log.jsonl`` — the
git-diffable SSoT that has always existed.

Paperclip environment: decisions route to a shared sink so a whole team (dev,
designer, …) reads the same memory instead of each machine diverging.

Selection is automatic: ``CHE_ENV=paperclip``, or the presence of any
``PAPERCLIP_*`` variable, opts into the Paperclip backend. The filesystem
backend is the default and preserves current behaviour exactly.

The Paperclip backend is a seam. The spike implementation writes to a shared
JSONL file under ``$PAPERCLIP_HOME/che-shared/`` (the Paperclip data volume) so
the routing is observable and testable without credentials. The production
target — a ``che_decisions`` table in Paperclip's Postgres — is specified in
ADR-0002 and lands behind the same ``DecisionStore`` interface without touching
callers.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Protocol

from che_core.decisions import append_decision_jsonl

PAPERCLIP_ENV_HINTS = ("PAPERCLIP_INSTANCE_ID", "PAPERCLIP_HOME", "PAPERCLIP_DEPLOYMENT_MODE")


def detect_env() -> str:
    """Return ``"paperclip"`` or ``"filesystem"`` from the process environment."""
    if os.environ.get("CHE_ENV", "").strip().lower() == "paperclip":
        return "paperclip"
    if any(os.environ.get(key) for key in PAPERCLIP_ENV_HINTS):
        return "paperclip"
    return "filesystem"


class DecisionStore(Protocol):
    def append(
        self,
        worktree_root: str,
        event_type: str,
        payload_s: str = "{}",
        ts_override: Optional[str] = None,
        session_id: Optional[str] = None,
        spec_id: Optional[str] = None,
    ) -> None: ...


def _parse_nullable(value):
    return None if value in (None, "null", "None", "", "NONE") else value


class FilesystemDecisionStore:
    """Current behaviour: append to ``decisions.log.jsonl`` (git SSoT)."""

    def append(self, worktree_root, event_type, payload_s="{}", ts_override=None, session_id=None, spec_id=None):
        append_decision_jsonl(
            worktree_root,
            event_type,
            payload_s,
            ts_override=ts_override,
            session_id=session_id,
            spec_id=spec_id,
        )


class PaperclipDecisionStore:
    """Route decisions to a shared, team-visible sink.

    Spike: a JSONL file under ``$PAPERCLIP_HOME/che-shared/`` (the Paperclip data
    volume), so every human and agent in the company reads the same memory.
    ADR-0002 specifies the production path (``che_decisions`` in Postgres) behind
    this same interface.
    """

    def __init__(self) -> None:
        self.shared_dir = Path(os.environ.get("PAPERCLIP_HOME", "/paperclip")) / "che-shared"

    def append(self, worktree_root, event_type, payload_s="{}", ts_override=None, session_id=None, spec_id=None):
        self.shared_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.shared_dir / "decisions.jsonl"

        ts = ts_override or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            payload = json.loads(payload_s)
            if not isinstance(payload, dict):
                payload = {"value": payload}
        except Exception:
            payload = {"raw": payload_s}

        entry = {
            "ts": ts,
            "event": event_type,
            "spec_id": _parse_nullable(spec_id),
            "session_id": _parse_nullable(session_id),
            "worktree_root": worktree_root,
            "data": payload,
            "_v": 1,
        }
        line = json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with open(out_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        print(f"[che] paperclip mode: decision routed to shared store {out_path}", file=sys.stderr)


def get_decision_store() -> DecisionStore:
    return PaperclipDecisionStore() if detect_env() == "paperclip" else FilesystemDecisionStore()


def append_decision(worktree_root, event_type, payload_s="{}", ts_override=None, session_id=None, spec_id=None):
    """Dispatch a decision append to the active backend."""
    get_decision_store().append(
        worktree_root,
        event_type,
        payload_s,
        ts_override=ts_override,
        session_id=session_id,
        spec_id=spec_id,
    )
