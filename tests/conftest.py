"""Shared test helpers for the flat Che layout.

Every test that needs storage paths must go through a real, *bound* worktree:
``compute_paths`` deliberately refuses to guess a project from the current working
directory, which is exactly the failure mode the flat layout was introduced to
eliminate (decisions and artifacts landing in different trees).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, Tuple

import pytest

GIT_ENV = ["-c", "user.email=test@che.local", "-c", "user.name=Che Test"]

#: Git exports these to its hook subprocesses. When pytest itself runs from inside
#: a hook (pre-commit / pre-push), an inherited GIT_DIR or GIT_INDEX_FILE makes the
#: throwaway repos created here operate on the OUTER repository instead — the
#: commit then fails or, worse, pollutes the real index. Always strip them.
_GIT_ENV_VARS_TO_STRIP = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_PREFIX",
)


def isolated_git_env() -> dict:
    """Environment for git calls that must never touch the outer repository."""
    env = os.environ.copy()
    for var in _GIT_ENV_VARS_TO_STRIP:
        env.pop(var, None)
    return env


def make_git_repo(path: Path) -> Path:
    """Create a minimal git repo (one empty commit) at ``path``."""
    path.mkdir(parents=True, exist_ok=True)
    env = isolated_git_env()
    subprocess.run(
        ["git", "-C", str(path), "init", "-q", "-b", "main"],
        check=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(
        ["git", "-C", str(path), *GIT_ENV, "commit", "-q", "--allow-empty", "-m", "init"],
        check=True,
        capture_output=True,
        env=env,
    )
    return path


def bind_worktree(
    tmp_path: Path,
    *,
    project: str = "acme",
    name: str = "main",
    session_id: str = "test-session",
) -> Tuple[Path, Dict[str, str]]:
    """Create a git repo + flat project + bound worktree under an isolated root.

    Returns ``(repo_root, paths)`` where ``paths`` is the ``compute_paths`` map.
    """
    from che_core.paths import ensure_session_dirs
    from che_core.workspaces import init_project
    from che_core.worktrees import add_worktree

    root = tmp_path / "che-workspaces"
    root.mkdir(parents=True, exist_ok=True)
    os.environ["CHE_WORKSPACES_ROOT"] = str(root)

    repo = make_git_repo(tmp_path / "repo")
    init_project(str(repo), slug=project)
    add_worktree(project, str(repo), name)

    paths = ensure_session_dirs(str(repo), session_id)
    return repo, paths


@pytest.fixture
def bound_worktree(tmp_path, monkeypatch):
    """``(repo_root, paths)`` for a git repo bound as project ``acme``/worktree ``main``."""
    monkeypatch.setenv("CHE_WORKSPACES_ROOT", str(tmp_path / "che-workspaces"))
    return bind_worktree(tmp_path)


@pytest.fixture
def che_ws_root(tmp_path, monkeypatch) -> Path:
    """Isolated ``CHE_WORKSPACES_ROOT`` with no project created yet."""
    root = tmp_path / "che-workspaces"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CHE_WORKSPACES_ROOT", str(root))
    return root
