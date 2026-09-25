"""Worktree lifecycle — the only Che concept that binds a filesystem path.

A project is an organising abstraction; a **worktree** is what points at a real
repository checkout. Adding the same worktree twice is a no-op that reuses the
existing tree, which is what gives a worktree multi-session memory instead of one
folder per session.

Binding record (``<worktree-dir>/.binding.json``)::

    {
      "project": "acme",
      "name": "main",
      "path": "/home/me/code/acme",      # absolute, git-checked
      "branch": "main",
      "origin": "git@github.com:acme/acme.git",
      "is_git": true,
      "created_at": "...",
      "updated_at": "..."
    }
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from che_core.diagnostics import fail
from che_core.project_layout import (
    DOMAIN_SLUGS,
    assert_no_cwd_dependency,
    assert_project_slug,
    get_project_dir,
    get_trash_dir,
    get_workspaces_root,
    get_worktree_dir,
    get_worktrees_dir,
    git_branch,
    git_origin,
    is_git_repo,
    project_exists,
    validate_slug,
)

BINDING_FILENAME = ".binding.json"

# Artifact subfolders are NOT pre-created. `output_path` already creates the
# parent directory of every artifact on demand (see che_core/paths.py), so an
# eager list here only produced empty directories and — worse — a second list
# that had to stay in sync with `_OUTPUT_SUBFOLDERS` and did not. A worktree is
# born with nothing but its binding, and grows a folder the first time it has
# something to put in it.


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def binding_path(project_slug: str, worktree_name: str) -> Path:
    return get_worktree_dir(project_slug, worktree_name) / BINDING_FILENAME


def read_binding(project_slug: str, worktree_name: str) -> Optional[Dict[str, Any]]:
    """Read the binding record of a worktree, or ``None`` when absent/corrupt."""
    bp = binding_path(project_slug, worktree_name)
    if not bp.is_file():
        return None
    try:
        with open(bp, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def worktree_exists(project_slug: str, worktree_name: str) -> bool:
    return binding_path(project_slug, worktree_name).is_file()


def add_worktree(
    project_slug: str,
    repo_path: str,
    worktree_name: str,
    *,
    force: bool = False,
) -> Dict[str, Any]:
    """Bind ``repo_path`` to ``<project>/worktrees/<worktree_name>/``.

    Idempotent: re-running with the same project + name **reuses** the existing
    tree and refreshes the recorded branch instead of creating a duplicate.

    Preconditions:
      - ``project_slug`` is non-empty and the project folder exists.
      - ``repo_path`` is an existing directory inside a git working tree.
      - ``worktree_name`` is a valid slug.

    Returns a JSON-serialisable report. Exits 2 on a precondition violation
    (usage-class failure) and 3 when the project is unknown.
    """
    assert_project_slug(project_slug)
    validate_slug(worktree_name, label="worktree_name")

    if not repo_path:
        fail("MISSING_REPO_PATH")

    resolved_repo = Path(repo_path).expanduser().resolve()
    assert_no_cwd_dependency(resolved_repo)

    if not resolved_repo.is_dir():
        fail("NOT_A_DIRECTORY", path=resolved_repo)

    if not project_exists(project_slug):
        fail("UNKNOWN_PROJECT", project_slug=project_slug)

    # R4 — both project and worktree require git. Refuse instead of best-effort.
    if not is_git_repo(str(resolved_repo)):
        fail("NOT_A_GIT_REPOSITORY", path=resolved_repo, subject="worktrees")

    worktree_dir = get_worktree_dir(project_slug, worktree_name)
    assert_no_cwd_dependency(worktree_dir)

    existing = read_binding(project_slug, worktree_name)
    reused = worktree_dir.is_dir() and existing is not None

    if worktree_dir.exists() and existing is None and not force:
        fail("REFUSED_UNMANAGED_DIRECTORY", path=worktree_dir, binding=BINDING_FILENAME)

    worktree_dir.mkdir(parents=True, exist_ok=True)

    now = _timestamp()
    binding = {
        "project": project_slug,
        "name": worktree_name,
        "path": str(resolved_repo),
        "branch": git_branch(str(resolved_repo)),
        "origin": git_origin(str(resolved_repo)),
        "is_git": True,
        "created_at": (existing or {}).get("created_at", now),
        "updated_at": now,
    }
    with open(worktree_dir / BINDING_FILENAME, "w", encoding="utf-8") as f:
        json.dump(binding, f, ensure_ascii=False, indent=2, sort_keys=True)

    # A-2 (SPEC lean-worktree-layout §4.7). With the artifact subfolders now
    # created lazily by `output_path`, the binding is the ONLY thing this
    # function produces — so if it is missing the worktree is unusable and the
    # success report below would be a lie. Impossible in correct code: crash.
    if not (worktree_dir / BINDING_FILENAME).is_file():
        fail(
            "UNEXPECTED",
            detail=(
                f"INVARIANT VIOLATED: {worktree_dir / BINDING_FILENAME} missing after write; "
                "the worktree was never bound."
            ),
        )

    return {
        "added": not reused,
        "reused": reused,
        "project": project_slug,
        "worktree": worktree_name,
        "path": str(resolved_repo),
        "branch": binding["branch"],
        "worktree_dir": str(worktree_dir),
        "decisions_path": str(worktree_dir / "decisions.log.jsonl"),
    }


def list_worktrees(project_slug: str) -> List[Dict[str, Any]]:
    """Every bound worktree of a project, sorted by name.

    A child whose name is not a valid slug is **skipped**, not rejected. Such a
    folder cannot be a worktree — ``get_worktree_dir`` refuses it — but raising
    here would take the whole machine down: ``list_projects`` and
    ``find_worktree_by_path`` both iterate through this function, so a single
    pre-flattening leftover (`<repo>__<branch>`, uppercase, underscore) made
    ``che project list`` die with a traceback and left every path lookup in
    that project unresolvable.
    """
    assert_project_slug(project_slug)
    wt_root = get_worktrees_dir(project_slug)
    if not wt_root.is_dir():
        return []

    out: List[Dict[str, Any]] = []
    for child in sorted(wt_root.iterdir()):
        if not child.is_dir():
            continue
        try:
            validate_slug(child.name, label="worktree_name")
        except ValueError:
            continue
        binding = read_binding(project_slug, child.name)
        if binding is None:
            continue
        binding.setdefault("name", child.name)
        binding["worktree_dir"] = str(child)
        out.append(binding)
    return out


def show_worktree(project_slug: str, worktree_name: str) -> Dict[str, Any]:
    binding = read_binding(project_slug, worktree_name)
    if binding is None:
        fail("UNKNOWN_WORKTREE", worktree_name=worktree_name, project_slug=project_slug)
    binding["worktree_dir"] = str(get_worktree_dir(project_slug, worktree_name))
    return binding


def find_worktree_by_path(repo_path: str) -> List[Dict[str, Any]]:
    """Reverse lookup: which (project, worktree) pairs bind this repository path?

    Used by the session binding hook to resolve context from a path without ever
    falling back to the current working directory.
    """
    if not repo_path:
        return []
    target = str(Path(repo_path).expanduser().resolve())

    root = get_workspaces_root()
    if not root.is_dir():
        return []

    matches: List[Dict[str, Any]] = []
    for project_dir in sorted(root.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith("."):
            continue
        # Pre-flattening leftovers live under the same root (e.g. a workspace
        # folder named `Flockr`, or `workspaces/`). They are not flat projects:
        # invalid slugs and folders without a `worktrees/` child must be skipped
        # rather than raising, otherwise every path lookup would break for users
        # who have not migrated yet.
        try:
            validate_slug(project_dir.name)
        except ValueError:
            continue
        if not (project_dir / "worktrees").is_dir():
            continue
        for binding in list_worktrees(project_dir.name):
            if binding.get("path") == target:
                matches.append(binding)
    return matches


def _write_manifest(trash_target: Path, *, original_path: str, slug: str) -> None:
    manifest = {
        "kind": "worktree",
        "slug": slug,
        "original_path": original_path,
        "moved_at": _timestamp(),
        "restore_hint": f"move {trash_target} back to {original_path}",
    }
    with open(trash_target / "_MANIFEST.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def remove_worktree(
    project_slug: str,
    worktree_name: str,
    *,
    dry_run: bool = True,
    confirmed: bool = False,
) -> Dict[str, Any]:
    """Trash-safe removal of a worktree folder (never ``rm -rf``).

    The bound repository is **never** touched — only ``<project>/worktrees/<name>/``.
    """
    binding = read_binding(project_slug, worktree_name)
    if binding is None:
        fail("UNKNOWN_WORKTREE", worktree_name=worktree_name, project_slug=project_slug)

    worktree_dir = get_worktree_dir(project_slug, worktree_name)
    plan = {
        "action": "move-to-trash",
        "project": project_slug,
        "worktree": worktree_name,
        "from": str(worktree_dir),
        "bound_repo_path": binding.get("path"),
        "repo_path_untouched": True,
        "dry_run": dry_run,
    }

    if dry_run:
        plan["applied"] = False
        plan["next"] = "Re-run with --no-dry-run --confirm to apply."
        return plan

    if not confirmed:
        fail("REFUSED_WITHOUT_CONFIRM")

    trash_root = get_trash_dir()
    trash_root.mkdir(parents=True, exist_ok=True)
    trash_slug = f"worktree--{project_slug}--{worktree_name}--{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    trash_target = trash_root / trash_slug

    shutil.move(str(worktree_dir), str(trash_target))
    _write_manifest(trash_target, original_path=str(worktree_dir), slug=trash_slug)

    plan.update(
        {
            "applied": True,
            "trash_path": str(trash_target),
            "trash_slug": trash_slug,
        }
    )
    return plan


def ensure_project_skeleton(project_slug: str) -> Dict[str, Any]:
    """Create the flat project skeleton: 8 domain folders, ``worktrees/``, ``_db/``.

    Idempotent — existing folders are left untouched.
    """
    assert_project_slug(project_slug)
    project_dir = get_project_dir(project_slug)
    assert_no_cwd_dependency(project_dir)

    created: List[str] = []
    for name in list(DOMAIN_SLUGS) + ["worktrees", "_db", "roles"]:
        target = project_dir / name
        if not target.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            created.append(str(target))
    return {"project_dir": str(project_dir), "created": created}
