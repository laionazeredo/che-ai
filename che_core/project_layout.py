"""Flat project/worktree layout — single source of truth for Che storage paths.

Layout (Sep 2026 flattening — the L1 "workspace" grouping level is gone)::

    ~/.che-workspaces/
    ├── .state/registry.jsonl        # session -> worktree -> project bindings
    ├── .trash/                      # trash-safe removals (never rm -rf)
    └── <project-slug>/
        ├── _db/                     # per-project SQLite (state store + RAG)
        ├── roles/                   # project-level human roles
        ├── business/ product/ design/ engineering/ devops/
        ├── copywriting/ social/ seo-analytics/     # canonical handoff docs
        └── worktrees/<worktree-name>/
            ├── .binding.json        # bound repo path + branch + git flag
            ├── decisions.log.jsonl
            └── specs|tasks|qa|reports|...

Contract notes:

* A **project** is an organising abstraction: it has a stable slug and a folder,
  but it does NOT bind a filesystem path. Only a **worktree** binds a path.
* Every command that writes artifacts must be given a project (and, when the
  artifact is worktree-scoped, a worktree).
* Nothing here may ever resolve through ``os.getcwd()`` — resolution is driven by
  explicit arguments only (that was the root cause of the historical split where
  decisions landed in a different tree than the artifacts).
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Optional

# --- Canonical domains -------------------------------------------------------

#: Canonical domain slugs. These name both the harness playbooks (`domains/<slug>/`)
#: and the per-project artifact folders (`<project>/<slug>/`).
DOMAIN_SLUGS = (
    "business",
    "product",
    "design",
    "engineering",
    "devops",
    "copywriting",
    "social",
    "seo-analytics",
)

#: Legacy slugs accepted on input and normalised to a canonical one. The
#: ``ux`` -> ``design`` rename is deliberately deferred: the harness playbook folder
#: is still ``domains/ux/``, so we alias instead of breaking it.
DOMAIN_SLUG_ALIASES = {
    "ux": "design",
    "operation": "devops",
    "ops": "devops",
    "dev": "engineering",
    "eng": "engineering",
}

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_MAX_SLUG_LEN = 63

#: Project-level singleton documents, kept at the project root during the
#: transition. Relocating them into their owning domain folder is a separate
#: increment (it would break the skills that reference these paths today).
PROJECT_DOCS = {
    "CHE_ARCHITECTURE_DOC": "architecture.md",
    "CHE_PROJECT_PROFILE": "project_profile.md",
    "CHE_PRODUCT_CONTEXT": "product_context.md",
    "CHE_ROADMAP_DOC": "roadmap.md",
}


# --- Primitives --------------------------------------------------------------


def validate_slug(slug: str, *, label: str = "slug") -> str:
    """Return ``slug`` unchanged when it is a valid lowercase identifier.

    Preconditions: ``slug`` is a non-empty string.
    Postcondition: returns the slug, or raises ``ValueError`` describing the
    violation (DbC fail-fast at the boundary instead of corrupting a path later).
    """
    if not slug:
        raise ValueError(f"{label} is required and must be a non-empty string")
    if len(slug) > _MAX_SLUG_LEN:
        raise ValueError(f"{label}={slug!r} exceeds {_MAX_SLUG_LEN} characters")
    if not _SLUG_RE.match(slug):
        raise ValueError(
            f"{label}={slug!r} is not a valid slug. Expected lowercase letters, digits and dashes, starting with alnum."
        )
    return slug


def normalise_domain(slug: str) -> str:
    """Map a legacy domain slug onto its canonical form.

    ``ux`` -> ``design`` and ``operation`` -> ``devops`` are the pending renames;
    everything else passes through after validation.
    """
    cleaned = (slug or "").strip().lower()
    cleaned = DOMAIN_SLUG_ALIASES.get(cleaned, cleaned)
    if cleaned not in DOMAIN_SLUGS:
        raise ValueError(f"Unknown domain {slug!r}. Expected one of: {', '.join(DOMAIN_SLUGS)}")
    return cleaned


def get_workspaces_root() -> Path:
    """Resolve the Che storage root (``~/.che-workspaces`` by default).

    Honours ``CHE_WORKSPACES_ROOT``, then the legacy ``HARNESS_SESSIONS_ROOT``,
    then the pre-2026 ``~/code/harness-sessions`` layout while it is the only one
    present.
    """
    env_root = os.environ.get("CHE_WORKSPACES_ROOT") or os.environ.get("HARNESS_SESSIONS_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    old_default = Path.home() / "code" / "harness-sessions"
    new_default = Path.home() / ".che-workspaces"

    if old_default.is_dir() and not new_default.is_dir():
        return old_default
    return new_default


def get_state_dir() -> Path:
    """``<root>/.state`` — user state that must NOT live in the Che source package."""
    return get_workspaces_root() / ".state"


def get_state_registry_path() -> Path:
    """``<root>/.state/registry.jsonl`` — session/worktree/project bindings."""
    return get_state_dir() / "registry.jsonl"


def get_trash_dir() -> Path:
    """``<root>/.trash`` — every destructive operation lands here, never ``rm -rf``."""
    return get_workspaces_root() / ".trash"


# --- Project -----------------------------------------------------------------


def get_project_dir(project_slug: str) -> Path:
    """``<root>/<project-slug>`` — the project folder."""
    validate_slug(project_slug, label="project_slug")
    return get_workspaces_root() / project_slug


def project_exists(project_slug: str) -> bool:
    return get_project_dir(project_slug).is_dir()


def get_db_dir(project_slug: str) -> Path:
    return get_project_dir(project_slug) / "_db"


def get_roles_dir(project_slug: str) -> Path:
    return get_project_dir(project_slug) / "roles"


def get_domain_dir(project_slug: str, domain: str) -> Path:
    """``<project>/<canonical-domain>`` — canonical handoff documents for a domain."""
    return get_project_dir(project_slug) / normalise_domain(domain)


def get_project_doc(project_slug: str, key: str) -> Optional[Path]:
    """Resolve one of :data:`PROJECT_DOCS` by its exported variable name."""
    filename = PROJECT_DOCS.get(key)
    if not filename:
        return None
    return get_project_dir(project_slug) / filename


# --- Worktree ----------------------------------------------------------------


def get_worktrees_dir(project_slug: str) -> Path:
    return get_project_dir(project_slug) / "worktrees"


def get_worktree_dir(project_slug: str, worktree_name: str) -> Path:
    """``<project>/worktrees/<name>`` — where every worktree-scoped artifact lives."""
    validate_slug(worktree_name, label="worktree_name")
    return get_worktrees_dir(project_slug) / worktree_name


# --- Append-only JSONL (shared by registry + decisions) ----------------------

#: Maximum size of a single JSONL record. Beyond this the write is refused rather
#: than risk a truncated line, which would break every subsequent reader.
MAX_JSONL_LINE_BYTES = 8192


def append_line_atomic(path: Path, line: str, *, max_bytes: int = MAX_JSONL_LINE_BYTES) -> None:
    """Append one complete line to a JSONL file, or refuse the write.

    Concurrent writers sharing a file must not interleave halves of a line. A
    single ``os.write`` under ``O_APPEND`` performs an atomic offset-advance plus
    write on POSIX, so readers always observe whole lines.

    Preconditions:
      - ``line`` contains no newline and encodes to at most ``max_bytes``.
    Postcondition: the file grows by exactly one complete, parseable line.
    """
    if not line:
        raise ValueError("append_line_atomic: line is required")
    if "\n" in line or "\r" in line:
        raise ValueError("append_line_atomic: line must not contain newlines")

    data = (line + "\n").encode("utf-8")
    if len(data) > max_bytes:
        raise ValueError(
            f"append_line_atomic: refusing a {len(data)}-byte record (limit {max_bytes}). "
            "A truncated JSONL line would corrupt every later reader."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


# --- Assertions (CANONICAL #3 — impossible states must crash) -----------------


def assert_project_slug(project_slug: str) -> None:
    """CRASH when a creating command is invoked without a usable project slug.

    A missing/blank slug here means the caller built the path from ambient state
    (cwd, env, guess). That is precisely the class of bug this module exists to
    eliminate, so it must never degrade into a silent default.
    """
    if not project_slug or not str(project_slug).strip():
        raise AssertionError(
            "INVARIANT VIOLATED: project_slug is empty. Every creating command must receive "
            "an explicit project slug (see `che project list`)."
        )


def assert_no_cwd_dependency(resolved: Path) -> None:
    """CRASH when a resolved storage path is relative.

    Resolution must be argument-driven; a relative path means some caller let
    ``os.getcwd()`` leak into the layout.
    """
    if not resolved.is_absolute():
        raise AssertionError(f"INVARIANT VIOLATED: resolved storage path is not absolute: {resolved}")


# --- Git ---------------------------------------------------------------------

#: Git exports these to its hook subprocesses (and they survive into anything the
#: hook spawns). An inherited ``GIT_DIR`` makes ``git -C <some other path>``
#: answer about the OUTER repository, so ``is_git_repo`` would report a plain
#: directory as a working tree. Every probe below asks a question about an
#: explicit path, so it must not consult ambient git state to answer it.
_GIT_DISCOVERY_ENV_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_PREFIX",
)


def hermetic_git_env() -> dict:
    """Environment for git calls that must answer about ``-C <path>`` only."""
    env = os.environ.copy()
    for var in _GIT_DISCOVERY_ENV_VARS:
        env.pop(var, None)
    return env


def _git_probe(args: list) -> Optional[str]:
    """Run a git subcommand hermetically; ``None`` on failure or empty output."""
    try:
        res = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            env=hermetic_git_env(),
        )
    except OSError:
        return None
    if res.returncode != 0:
        return None
    return res.stdout.strip() or None


def is_git_repo(path: str) -> bool:
    """True when ``path`` is inside a git working tree.

    Worktrees and projects both require git (contract R4), so this is the gate
    every creating command uses instead of attempting best-effort creation.
    """
    if not path:
        return False
    probe = Path(path).expanduser()
    if not probe.is_dir():
        return False
    return _git_probe(["git", "-C", str(probe), "rev-parse", "--is-inside-work-tree"]) == "true"


def git_branch(path: str) -> Optional[str]:
    """Current branch of a git repo, or ``None`` when detached/not a repo."""
    branch = _git_probe(["git", "-C", str(Path(path).expanduser()), "rev-parse", "--abbrev-ref", "HEAD"])
    if branch == "HEAD":
        return None
    return branch


def git_origin(path: str) -> Optional[str]:
    """``origin`` remote URL of a git repo, if any."""
    return _git_probe(["git", "-C", str(Path(path).expanduser()), "remote", "get-url", "origin"])


def slug_from_origin(origin: Optional[str], fallback: str) -> str:
    """Derive a stable project slug from a git origin URL.

    ``git@github.com:acme/shop.git`` -> ``github-com-acme-shop``. Used only as a
    *suggestion*: ``che project init`` still requires the user to pass ``--slug``
    explicitly, so identity never depends on ambient git state.
    """
    if not origin:
        return fallback
    raw = re.sub(r"^(https?://|git@|ssh://|git://)", "", origin)
    raw = re.sub(r"\.git$", "", raw)
    raw = re.sub(r"^[^:]+:", "/", raw)
    return re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-") or fallback
