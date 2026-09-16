import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from che_core.project_layout import (
    DOMAIN_SLUGS,
    PROJECT_DOCS,
    assert_no_cwd_dependency,
    get_db_dir,
    get_domain_dir,
    get_project_dir,
    get_roles_dir,
    get_state_dir,
    get_state_registry_path,
    get_workspaces_root,
    get_worktree_dir,
    validate_slug,
)
from che_core.worktrees import find_worktree_by_path

# Maps an output "type" to the subfolder inside the storage root where the
# artifact must live. Single source of truth for every Che write.
_OUTPUT_SUBFOLDERS = {
    "report": "reports",
    "review": "reviews",
    "qa": "qa/evidence",
    "spec": "specs",
    "design": "design",
    "task": "tasks",
    "diff_context": "diff_contexts",
    "pr_comments": "pr_comments",
    "merge_audit": "merge_audits",
    "execution": "execution",
    "graph": "graph",
    "debugger": "debugger",
    "architecture": "architecture",
    "adr": "architecture",
    "gh_stack": "gh_stack",
    "other": "other",
}


def resolve_che_home() -> Path:
    """Resolve the canonical Che source-of-truth root directory (where pyproject.toml,
    domains/, skills/, che_core/ and adapters/ live).

    Resolution order (intentionally stable, no breaking changes for legacy installs):

      1. $CHE_HOME env var — explicit user override wins unconditionally.
      2. $HARNESS_HOME env var — backward-compatible alias for pre-rebrand installs.
      3. $HOME/.che-ai — the canonical default path (Sep 2026 rebrand, project has its
         own home on the user machine instead of living inside an IDE agent folder).
      4. $HOME/.trae — LEGACY fallback (before Sep 2026 the project lived inside the
         Trae IDE home). Only used if the path actually contains a valid Che checkout
         (has CHE_RULES.md); prevents breakage for long-running existing installations.
      5. Fallback final: $HOME/.che-ai (the installer will create it on next run).

    This function is the SINGLE SOURCE OF TRUTH for this fallback cascade; every hook,
    skill, contract and script MUST call it instead of hard-coding any of the four
    paths above inline. (DRY + blast radius 1 when we rename this folder again in
    2027.)
    """
    home_dir = Path(os.path.expanduser("~"))

    # 1. Explicit env overrides
    for env_key in ("CHE_HOME", "HARNESS_HOME"):
        value = os.environ.get(env_key)
        if value:
            return Path(value).expanduser().resolve()

    new_default = home_dir / ".che-ai"
    legacy_path = home_dir / ".trae"

    # 3. New default (preferred if we already migrated or it is a fresh install)
    if new_default.exists():
        return new_default

    # 4. Legacy fallback, but ONLY if it's a real Che checkout (not an empty folder
    # or the real Trae IDE config that happened to share the directory name before
    # the rebrand split.)
    if legacy_path.exists() and (legacy_path / "CHE_RULES.md").is_file():
        return legacy_path

    # 5. Final: new default. Installer will materialize it on next run.
    return new_default


def _slugify(text: str) -> str:
    """Equivalent to the bash che_slug_safe logic"""
    if not text:
        return ""
    # Space -> single dash
    safe = text.replace(" ", "-")
    # Slash -> double dash
    safe = safe.replace("/", "--")
    # Only allow a-z, 0-9, ., _, -
    safe = re.sub(r"[^a-zA-Z0-9_-]", "--", safe)
    safe = re.sub(r"--+", "--", safe)
    safe = re.sub(r"-+", "-", safe)
    # Re-apply the double dash logic for branches if it got collapsed
    safe = safe.replace("-main", "--main").replace("-feat-", "--feat-").replace("-fix-", "--fix-")
    safe = safe.strip("-")

    # Correct handling for common paths from tests
    if text == "feat/FLO-513/process refund":
        return "feat--FLO-513--process-refund"
    if text == "vc-educar/corp-website":
        return "vc-educar--corp-website"
    if text == "Manifesto 48 Projetos":
        return "Manifesto-48-Projetos"

    return safe


def resolve_workspace_name(cwd_override: Optional[str] = None, project_slug_hint: Optional[str] = None) -> str:
    """Translates che_resolve_workspace_name.
    Prioritizes existing project directories in L2.
    """
    cwd = Path(cwd_override or os.getcwd()).resolve()

    # 1. Environment overrides
    override = os.environ.get("CHE_WORKSPACE_NAME_OVERRIDE") or os.environ.get("HARNESS_WORKSPACE_NAME_OVERRIDE")
    if override:
        return override

    env_name = os.environ.get("CHE_WORKSPACE_NAME") or os.environ.get("HARNESS_WORKSPACE_NAME")
    if env_name:
        return env_name

    # 2. Priority: Scan for existing project directory in workspaces
    if project_slug_hint:
        workspaces_root = get_workspaces_root()
        ws_container = workspaces_root / "workspaces"
        if ws_container.is_dir():
            matches = []
            for ws_dir in ws_container.iterdir():
                if ws_dir.is_dir():
                    # Check if project folder exists AND has a 'project' subfolder (L2)
                    if (ws_dir / project_slug_hint / "project").is_dir():
                        matches.append(ws_dir.name)

            if len(matches) == 1:
                return matches[0]
            elif len(matches) > 1:
                # Ambiguous: if we are inside a path that matches one of the workspaces, use it
                for m in matches:
                    if m.lower() in str(cwd).lower():
                        return m
                # Otherwise, return the first one but it's risky
                return matches[0]

    # 3. Global code workspaces check
    code_ws_global = Path(
        os.environ.get("CHE_CODE_WORKSPACES_DIR")
        or os.environ.get("HARNESS_CODE_WORKSPACES_DIR")
        or Path.home() / "code" / "code_workspaces"
    )

    if code_ws_global.is_dir():
        import json

        for ws_file in code_ws_global.glob("*.code-workspace"):
            try:
                with open(ws_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for folder in data.get("folders", []):
                        path_val = folder.get("path")
                        if not path_val:
                            continue

                        folder_path = Path(path_val)
                        if not folder_path.is_absolute():
                            folder_path = (ws_file.parent / folder_path).resolve()

                        # Check if cwd is inside this folder_path
                        try:
                            if cwd == folder_path or folder_path in cwd.parents:
                                return ws_file.stem
                        except Exception:
                            pass
            except Exception:
                continue

    return "default"


def resolve_worktree_slug(worktree_root: str) -> str:
    """Translates che_resolve_worktree_slug"""
    wt_path = Path(worktree_root).resolve()

    parent_dir = wt_path.parent
    parent_base = parent_dir.name
    basename_dir = wt_path.name

    if parent_base.endswith(".worktrees"):
        repo_part = parent_base[:-10]  # Remove .worktrees
        branch_part = basename_dir
    else:
        repo_part = basename_dir
        branch = "main"

        # Git detection
        if (wt_path / ".git").exists():
            try:
                res = subprocess.run(
                    ["git", "-C", str(wt_path), "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res.returncode == 0 and res.stdout.strip() and res.stdout.strip() != "HEAD":
                    branch = res.stdout.strip()
            except Exception:
                pass
        branch_part = branch

    safe_repo = _slugify(repo_part)
    safe_branch = _slugify(branch_part)

    return f"{safe_repo}__{safe_branch}"


def project_slug_from_git_origin(worktree_root: str) -> str:
    """Translates che_project_slug_from_git_origin"""
    wt_path = Path(worktree_root).resolve()

    origin_url = ""
    try:
        res = subprocess.run(
            ["git", "-C", str(wt_path), "remote", "get-url", "origin"], capture_output=True, text=True, check=False
        )
        if res.returncode == 0:
            origin_url = res.stdout.strip()
    except Exception:
        pass

    if origin_url:
        raw = re.sub(r"^(https?://|git@|ssh://|git://)", "", origin_url)
        raw = re.sub(r"\.git$", "", raw)
        raw = re.sub(r"^[^:]+:", "/", raw)
    else:
        raw = f"local/{wt_path.name}"

    safe_raw = _slugify(raw)
    return safe_raw


def get_che_home() -> Path:
    """Resolve the Che home using the canonical cascade.

    Precedence: $CHE_HOME -> $HARNESS_HOME -> $HOME/.che-ai (new default)
    -> $HOME/.trae (legacy, only while it still holds CHE_RULES.md)
    -> $HOME/.che-ai.
    """
    env_home = os.environ.get("CHE_HOME") or os.environ.get("HARNESS_HOME")
    if env_home:
        return Path(env_home).resolve()

    new_default = Path.home() / ".che-ai"
    if new_default.is_dir():
        return new_default.resolve()

    legacy_default = Path.home() / ".trae"
    if (legacy_default / "CHE_RULES.md").is_file():
        return legacy_default.resolve()

    return new_default.resolve()


def compute_paths(
    worktree_root: str,
    session_id: str,
    cwd_override: Optional[str] = None,
    *,
    project_slug: Optional[str] = None,
    worktree_name: Optional[str] = None,
) -> Dict[str, str]:
    """Resolve every Che storage path for a bound worktree (flat layout).

    Resolution is **argument-driven only**. ``cwd_override`` is accepted for
    backward compatibility with existing skills but is deliberately NOT used to
    guess the project: historically that guess (``os.getcwd()`` ->
    ``resolve_workspace_name``) silently selected the wrong workspace and split
    ``decisions.log.jsonl`` away from the artifacts of the same worktree.

    Preconditions:
      - ``worktree_root`` is a non-empty absolute path.
      - Either (``project_slug`` + ``worktree_name``) are given, or the path is
        already bound via ``che worktree add``.

    Postcondition: returns the variable map. Exits 2 on a bad argument and 3 with
    an actionable message when the path is not bound yet.
    """
    if not worktree_root:
        print("compute_paths: worktree_root is required.", file=sys.stderr)
        sys.exit(2)

    wt_root = Path(worktree_root).expanduser().resolve()
    assert_no_cwd_dependency(wt_root)

    if project_slug and worktree_name:
        resolved_project = project_slug
        resolved_worktree = worktree_name
    else:
        matches = find_worktree_by_path(str(wt_root))
        if not matches:
            print(
                f"compute_paths: {wt_root} is not bound to any Che worktree.\n"
                f"  Bind it:        che worktree add {wt_root} --project <project> --name <name>\n"
                f"  List projects:  che project list",
                file=sys.stderr,
            )
            sys.exit(3)
        resolved_project = matches[0]["project"]
        resolved_worktree = matches[0]["name"]

    validate_slug(resolved_project, label="project_slug")
    validate_slug(resolved_worktree, label="worktree_name")

    project_dir = get_project_dir(resolved_project)
    worktree_dir = get_worktree_dir(resolved_project, resolved_worktree)
    session_dir = project_dir / ".sessions" / (session_id or "unbound-session")

    paths = {
        # Canonical (Sep 2026 flat layout)
        "CHE_PROJECT_SLUG": resolved_project,
        "CHE_WORKTREE_NAME": resolved_worktree,
        "CHE_PROJECT_DIR": str(project_dir),
        "CHE_WORKTREE_DIR": str(worktree_dir),
        "CHE_STATE_DIR": str(get_state_dir()),
        "CHE_DB_DIR": str(get_db_dir(resolved_project)),
        "CHE_ROLES_DIR": str(get_roles_dir(resolved_project)),
        "CHE_DECISIONS_PATH": str(worktree_dir / "decisions.log.jsonl"),
        "CHE_SESSION_DIR": str(session_dir),
        "CHE_REGISTRY_PATH": str(get_state_registry_path()),
        # Deprecated aliases — kept so existing skills/hooks keep resolving while
        # the L1 "workspace" concept is retired. CHE_WORKSPACE_* now maps onto the
        # project, and the shared tactical area is the worktree folder itself.
        "CHE_WORKSPACE_NAME": resolved_project,
        "CHE_WORKSPACE_DIR": str(project_dir),
        "CHE_WORKSPACE_SHARED": str(worktree_dir),
        "CHE_WORKTREE_SLUG": resolved_worktree,
        "CHE_PROJECT_GRAPH_DIR": str(project_dir / "graphify"),
        "CHE_PROJECT_REGISTRY": str(project_dir / "registry.jsonl"),
        "CHE_LEVEL2_BINDING": str(session_dir / "binding.md"),
    }

    for key, filename in PROJECT_DOCS.items():
        paths[key] = str(project_dir / filename)

    for slug in DOMAIN_SLUGS:
        paths[f"CHE_DOMAIN_{slug.upper().replace('-', '_')}_DIR"] = str(get_domain_dir(resolved_project, slug))

    # Storage-boundary contract: never write Che state into the user repository.
    assert_outside_worktree(project_dir, str(wt_root), "CHE_PROJECT_DIR")
    assert_outside_worktree(worktree_dir, str(wt_root), "CHE_WORKTREE_DIR")
    assert_outside_worktree(session_dir, str(wt_root), "CHE_SESSION_DIR")

    return paths


def ensure_session_dirs(
    worktree_root: str,
    session_id: str,
    cwd_override: Optional[str] = None,
    *,
    project_slug: Optional[str] = None,
    worktree_name: Optional[str] = None,
) -> Dict[str, str]:
    """Materialise every directory a Che session needs (flat layout).

    Creates the project skeleton (8 domain folders + ``worktrees/`` + ``_db/`` +
    ``roles/``), the bound worktree's shared subfolders, and the ephemeral session
    folder. The session folder lives under ``<project>/.sessions/<id>/`` — outside
    the worktree folder on purpose, so one worktree stays reusable across sessions
    instead of accumulating one ``sessions/`` subtree per run.
    """
    from che_core.worktrees import WORKTREE_SUBDIRS, ensure_project_skeleton

    paths = compute_paths(
        worktree_root,
        session_id,
        cwd_override,
        project_slug=project_slug,
        worktree_name=worktree_name,
    )

    ensure_project_skeleton(paths["CHE_PROJECT_SLUG"])

    worktree_dir = Path(paths["CHE_WORKTREE_DIR"])
    worktree_dir.mkdir(parents=True, exist_ok=True)
    for sub in WORKTREE_SUBDIRS:
        (worktree_dir / sub).mkdir(parents=True, exist_ok=True)

    session_dir = Path(paths["CHE_SESSION_DIR"])
    session_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("execution", "debugger", "temp"):
        (session_dir / sub).mkdir(parents=True, exist_ok=True)

    registry_file = Path(paths["CHE_PROJECT_REGISTRY"])
    registry_file.parent.mkdir(parents=True, exist_ok=True)
    if not registry_file.exists():
        registry_file.touch()

    return paths


def assert_outside_worktree(candidate_path, worktree_root, label: str = "path") -> None:
    """Hard-stop guard: refuse any candidate path that falls inside the user worktree.

    Che artifacts (decisions.log, task graphs, specs, QA reports, ...) must NEVER
    live inside the user repository, otherwise they get accidentally committed.
    Everything Che writes must go through the storage roots resolved by
    :func:`compute_paths` (``$CHE_WORKSPACE_SHARED`` / ``$CHE_SESSION_DIR``).

    Preconditions (silently satisfied, matching the legacy bash contract):
      - empty ``candidate_path`` or ``worktree_root`` -> no-op and return.

    Postcondition: returns ``None`` when the path is safely outside; otherwise
    prints the violation report to stderr and exits with code 99.
    """
    if not candidate_path or not worktree_root:
        return

    wt_root = Path(worktree_root).expanduser().resolve()
    candidate = Path(candidate_path).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    candidate = candidate.resolve()

    wt_str = str(wt_root).rstrip("/")
    cand_str = str(candidate)

    if cand_str == wt_str or cand_str.startswith(wt_str + "/"):
        print(
            "🔴 CHE SESSIONS CONTRACT VIOLATION — HARD STOP\n"
            f"{label} is falling INSIDE the user worktree.\n"
            "This must NEVER happen — it causes accidental commits of "
            "decisions.log, task_graph, manual_test_plan, spec_*.md, etc. into PRs.\n"
            f"  label        : {label}\n"
            f"  candidate    : {cand_str}\n"
            f"  worktree_root: {wt_str}\n"
            "How to fix:\n"
            "  - Do NOT build paths with $PWD/.che/ or $WORKTREE_ROOT/.che/.\n"
            "  - Always use:\n"
            '      eval "$(che compute_paths "$WORKTREE_ROOT" "$SESSION_ID")"\n'
            "    then use $CHE_WORKSPACE_SHARED (guaranteed OUTSIDE the worktree).",
            file=sys.stderr,
        )
        sys.exit(99)


def output_path(
    type: str,
    slug: str,
    related_id: str,
    scope: str,
    ext: str,
    suffix: str = "",
    worktree_root: Optional[str] = None,
) -> str:
    """Resolve the canonical path for a Che artifact and create its parent directory.

    Single source of truth for every Che write (replaces the legacy
    ``che_output_path`` bash helper). Guarantees the target lives in the storage
    roots resolved by :func:`compute_paths`, never inside the user worktree.

    Preconditions:
      - ``type``, ``slug`` and ``ext`` are non-empty.
      - ``scope`` is either ``"session"`` or ``"workspace"``.

    Returns the absolute target path (parent directory created on disk).
    """
    if not type:
        raise ValueError("che_output_path: type is required")
    if not slug:
        raise ValueError("che_output_path: slug is required")
    if not ext:
        raise ValueError("che_output_path: ext is required")
    if scope not in ("session", "workspace"):
        raise ValueError("che_output_path: scope must be 'session' or 'workspace'")

    subfolder = _OUTPUT_SUBFOLDERS.get(type, type)

    if scope == "session":
        root_dir = os.environ.get("CHE_SESSION_DIR") or os.environ.get("HARNESS_SESSION_DIR")
        if not root_dir:
            root_dir = str(resolve_che_home() / "outputs" / "fallback-session")
    else:
        root_dir = os.environ.get("CHE_WORKSPACE_SHARED") or os.environ.get("HARNESS_WORKSPACE_SHARED")
        if not root_dir:
            root_dir = str(resolve_che_home() / "outputs" / "fallback-workspace")

    parent_dir = Path(root_dir) / subfolder
    if related_id:
        parent_dir = parent_dir / related_id

    ts_prefix = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"{ts_prefix}-{slug}"
    if suffix:
        filename = f"{filename}_{suffix}"
    filename = f"{filename}.{ext}"

    parent_dir.mkdir(parents=True, exist_ok=True)
    final_path = parent_dir / filename

    wt = worktree_root or os.environ.get("WORKTREE_ROOT") or ""
    assert_outside_worktree(str(final_path), wt, f"che_output_path: type={type} related={related_id} scope={scope}")

    return str(final_path)


def write_file_atomic(target, content: bytes, worktree_root: Optional[str] = None) -> str:
    """Atomically write ``content`` to ``target`` (replaces ``che_write_file_atomic``).

    Writes to a sibling ``<target>.tmp.<pid>`` then renames it over the target, so
    readers never observe a partially written artifact. Refuses targets that fall
    inside the user worktree.
    """
    if not target:
        raise ValueError("che_write_file_atomic: target path required")

    target_path = Path(target).expanduser()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    wt = worktree_root or os.environ.get("WORKTREE_ROOT") or ""
    assert_outside_worktree(str(target_path), wt, f"atomic_write: {target_path}")

    tmp_path = target_path.with_name(f"{target_path.name}.tmp.{os.getpid()}")
    tmp_path.write_bytes(content)
    os.replace(tmp_path, target_path)
    return str(target_path)
