"""Test freeze — the tests a slice locked, and the hash that proves nobody weakened them.

WHY THIS EXISTS
---------------
A green suite proves the tests pass, not that they still say what they said when the behaviour was
agreed. An agent that cannot make an assertion true can make the assertion weaker, and every gate
Che runs today — coverage, QA, scope-checker — stays green through that edit.

One primitive closes the hole: after a slice ships its tests, Che records their sha256. From then on
any change to a locked file is DRIFT — a fact this module reports, and which only the user can
authorise, with the old hash, the new hash and the reason kept in the manifest.

WHAT IT IS NOT
--------------
Not a test runner (that is che-qa), not a coverage check (that is `che spec coverage`), and not the
default. Locking is opt-in per task: a worktree with no manifest verifies as `unlocked`, which is a
pass, not a gap.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from che_core.diagnostics import fail
from che_core.paths import compute_paths, write_file_atomic

#: Bumped only when a reader would misinterpret an older file.
SCHEMA = 1

_RELATED_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_path(worktree_root: str, related_id: str) -> Path:
    """Resolve the lock file for one task in the worktree's durable area, never in the repository.

    PRE: ``related_id`` is a slug. POST: the parent folder is NOT created here — verifying a task
    that never locked anything must leave no trace on disk.
    """
    if not related_id or not _RELATED_ID.match(related_id):
        fail("TEST_LOCK_INVALID_RELATED_ID", related_id=related_id or "")
    # The session id is irrelevant to this path; compute_paths only needs one to name CHE_SESSION_DIR.
    paths = compute_paths(worktree_root, "test-lock")
    return Path(paths["CHE_WORKTREE_DIR"]) / "test-lock" / f"{related_id}.json"


def _load(path: Path) -> Optional[Dict[str, Any]]:
    """Read one manifest, or return None when this task never locked anything."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        fail("UNREADABLE_INPUT", path=str(path), detail=str(exc))
    except json.JSONDecodeError as exc:
        fail("INVALID_JSON", path=str(path), detail=str(exc))
    if not isinstance(data, dict) or not isinstance(data.get("locks"), dict):
        fail("INVALID_JSON", path=str(path), detail="expected an object with a `locks` map")
    return data


def _save(path: Path, data: Dict[str, Any], worktree_root: str) -> None:
    data["schema"] = SCHEMA
    data["updated_at"] = _now()
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    write_file_atomic(str(path), payload, worktree_root=worktree_root)


def _resolve_file(worktree_root: str, raw: str) -> "tuple[str, Path]":
    """Map a caller's path to ``(worktree-relative posix path, absolute path)``.

    PRE: the path names a file inside the bound worktree. A path outside it is refused rather than
    silently skipped: the scissor check (§19) makes the worktree the only writable scope.
    """
    wt_root = Path(worktree_root).expanduser().resolve()
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = wt_root / candidate
    candidate = candidate.resolve()
    try:
        relative = candidate.relative_to(wt_root)
    except ValueError:
        fail("TEST_LOCK_FILE_OUTSIDE_WORKTREE", file=str(raw), worktree_root=str(wt_root))
    if not candidate.is_file():
        fail("TEST_LOCK_FILE_MISSING", file=relative.as_posix())
    return relative.as_posix(), candidate


def record(worktree_root: str, related_id: str, files: Sequence[str]) -> Dict[str, Any]:
    """Lock the test files one slice just shipped.

    PRE: at least one file, every one of them inside the worktree.
    POST: each file is locked at its current sha256, or the whole call fails. A lock is never moved
    here — moving one is :func:`authorize`, which demands a reason and keeps both hashes.
    """
    if not files:
        fail("TEST_LOCK_NO_FILES")

    path = manifest_path(worktree_root, related_id)
    data = _load(path)
    if data is None:
        data = {
            "schema": SCHEMA,
            "related_id": related_id,
            "worktree_root": str(Path(worktree_root).expanduser().resolve()),
            "created_at": _now(),
            "locks": {},
        }

    locked: List[str] = []
    unchanged: List[str] = []
    drifted: List[str] = []
    for raw in files:
        relative, absolute = _resolve_file(worktree_root, raw)
        digest = _sha256(absolute)
        current = data["locks"].get(relative)
        if current is None:
            data["locks"][relative] = {"sha256": digest, "locked_at": _now(), "authorisations": []}
            locked.append(relative)
        elif current.get("sha256") == digest:
            unchanged.append(relative)
        else:
            drifted.append(relative)

    if drifted:
        # All-or-nothing: a partially applied record would hide which lock moved.
        fail("TEST_LOCK_DRIFT", files=", ".join(sorted(drifted)), related_id=related_id)

    _save(path, data, worktree_root)
    return {
        "ok": True,
        "status": "locked",
        "manifest": str(path),
        "related_id": related_id,
        "locked": sorted(locked),
        "unchanged": sorted(unchanged),
        "total_locked": len(data["locks"]),
    }


def verify(worktree_root: str, related_id: str) -> Dict[str, Any]:
    """Compare every locked file against the hash it was locked at.

    POST: ``ok`` is True when the task never locked anything (the mode is opt-in) or when every
    locked file still matches. Drift and deletion are reported per file, never as a bare count.
    """
    path = manifest_path(worktree_root, related_id)
    data = _load(path)
    if data is None:
        return {
            "ok": True,
            "status": "unlocked",
            "manifest": str(path),
            "related_id": related_id,
            "checked": 0,
            "drifted": [],
            "missing": [],
            "note": "no test lock recorded for this task",
        }

    wt_root = Path(worktree_root).expanduser().resolve()
    drifted: List[Dict[str, str]] = []
    missing: List[str] = []
    for relative, entry in sorted(data["locks"].items()):
        target = wt_root / relative
        if not target.is_file():
            missing.append(relative)
            continue
        actual = _sha256(target)
        expected = str(entry.get("sha256") or "")
        if actual != expected:
            drifted.append({"file": relative, "expected": expected, "actual": actual})

    ok = not drifted and not missing
    if ok:
        status = "ok"
    elif drifted:
        status = "drift"
    else:
        status = "missing"
    return {
        "ok": ok,
        "status": status,
        "manifest": str(path),
        "related_id": related_id,
        "checked": len(data["locks"]),
        "drifted": drifted,
        "missing": missing,
    }


def authorize(worktree_root: str, related_id: str, file: str, reason: str) -> Dict[str, Any]:
    """Re-lock one file after the user authorised changing it, keeping the audit trail.

    PRE: ``reason`` is the user's own words, non-empty; ``file`` is already locked.
    POST: the new hash becomes the lock, and ``{old_sha256, new_sha256, reason, at}`` is appended to
    that file's ``authorisations`` — so a later reader sees what was weakened, when and why.
    """
    if not reason or not reason.strip():
        fail("TEST_LOCK_REASON_REQUIRED")

    path = manifest_path(worktree_root, related_id)
    data = _load(path)
    if data is None:
        fail("TEST_LOCK_NOT_LOCKED", file=file, related_id=related_id)

    relative, absolute = _resolve_file(worktree_root, file)
    entry = data["locks"].get(relative)
    if entry is None:
        fail("TEST_LOCK_NOT_LOCKED", file=relative, related_id=related_id)

    new_digest = _sha256(absolute)
    old_digest = str(entry.get("sha256") or "")
    if new_digest == old_digest:
        return {
            "ok": True,
            "status": "unchanged",
            "file": relative,
            "sha256": new_digest,
            "manifest": str(path),
        }

    entry.setdefault("authorisations", []).append(
        {"at": _now(), "old_sha256": old_digest, "new_sha256": new_digest, "reason": reason.strip()}
    )
    entry["sha256"] = new_digest
    entry["locked_at"] = _now()
    _save(path, data, worktree_root)
    return {
        "ok": True,
        "status": "authorised",
        "file": relative,
        "old_sha256": old_digest,
        "new_sha256": new_digest,
        "reason": reason.strip(),
        "manifest": str(path),
    }
