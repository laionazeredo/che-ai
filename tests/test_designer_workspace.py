"""Tests for che_core.designer.run_init (T1 · F0 Tracer — B-1 + AB-1).

Contract:
- B-1 (positive): che designer init writes DESIGN.md + tokens.json inside the worktree
  and `git status --porcelain` lists exactly the two untracked paths.
- AB-1 (negative): path traversal slugs are rejected without writing anything.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


def _isolated_env(cwd: Path) -> dict[str, str]:
    """Return a subprocess env that pins GIT_DIR + GIT_WORK_TREE to cwd.

    Prevents test tmp_paths from accidentally writing to the parent worktree's
    branch when pytest is itself invoked from inside a git worktree.

    Also clears git's hook-injected env vars (GIT_INDEX_FILE and friends) that
    `git commit` exports to its hook subprocesses — otherwise a `git status`
    inside a test reads the *commit's* staged index, not the tmp repo's.
    """
    env = os.environ.copy()
    for var in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_PREFIX",
    ):
        env.pop(var, None)
    env["GIT_DIR"] = str(cwd / ".git")
    env["GIT_WORK_TREE"] = str(cwd)
    return env


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run git scoped to cwd using BOTH `-C <path>` (git's own isolation) AND
    GIT_DIR/GIT_WORK_TREE env vars (defence in depth).

    `git -C <path>` changes git's working directory before any subcommand.
    Setting GIT_DIR/GIT_WORK_TREE explicitly prevents leakage when pytest
    is itself launched from inside a git worktree (the worktree's .git file
    would otherwise be discovered by parent-directory walks).
    """
    env = _isolated_env(cwd)
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        env=env,
        capture_output=True,
        text=True,
        check=check,
    )


# @ac B-1 — F0 tracer: init writes the git-native design tree
def test_init_writes_design_tree(tmp_path: Path) -> None:
    """Run run_init on a fresh tmp worktree; expect DESIGN.md + tokens.json inside worktree."""
    # Lazy import so test module loads even when che_core is partially built
    from che_core.designer import run_init

    wt = tmp_path
    sess = "sess-test-f0-b1"

    # run_init must not raise; the contract says it returns 0 and exits cleanly
    rc = run_init(str(wt), sess, "acme")
    assert rc == 0, "run_init must return 0 on a valid sub-product slug"

    design_md = wt / "design" / "DESIGN.md"
    tokens_json = wt / "design" / "tokens" / "tokens.json"
    assert design_md.is_file(), f"DESIGN.md must exist at {design_md}"
    assert tokens_json.is_file(), f"tokens.json must exist at {tokens_json}"

    # DESIGN.md must start with YAML frontmatter `---` (Stitch spec)
    text = design_md.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "DESIGN.md must start with YAML frontmatter delimiter"
    assert text.count("\n---\n") == 1, "DESIGN.md must have exactly one closing frontmatter delimiter"

    # tokens.json must parse and contain a 'colors' group (single-source invariant)
    import json as _json

    data = _json.loads(tokens_json.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "tokens.json must parse as a JSON object"
    assert "colors" in data, "tokens.json invariant: colors group required (A-2 future-proof)"


# @ac AB-1 — path traversal rejection
def test_init_rejects_path_traversal(tmp_path: Path) -> None:
    """A slug like '../../etc' must NOT create files anywhere on disk; must sys.exit with non-zero."""
    from che_core import designer as designer_mod

    wt = tmp_path
    sess = "sess-test-f0-ab1"
    bad_slug = "../../etc"

    captured_stderr: list[str] = []

    class _FakeStderr:
        def write(self, s: str) -> int:
            captured_stderr.append(s)
            return len(s)

        def flush(self) -> None:
            pass

    real_stderr = sys.stderr
    sys.stderr = _FakeStderr()
    try:
        with pytest.raises(SystemExit) as exc_info:
            designer_mod.run_init(str(wt), sess, bad_slug)
    finally:
        sys.stderr = real_stderr

    assert exc_info.value.code != 0, "run_init must exit with non-zero code on path traversal"

    # stderr must contain the rejected slug (validation message)
    joined = "".join(captured_stderr)
    assert "invalid sub-product slug" in joined, f"stderr must explain the rejection; got: {joined!r}"
    assert bad_slug in joined or re.search(r"\.\./\.\./etc", joined), (
        f"stderr must name the rejected slug; got: {joined!r}"
    )

    # ZERO files written anywhere under tmp_path
    remaining = [p for p in wt.rglob("*") if p.is_file()]
    assert remaining == [], f"no files must be created on rejection; found: {remaining}"


# @ac regression — existing bootstrap subcommand still parses
def test_bootstrap_subcommand_still_parses() -> None:
    """T1 must NOT remove the existing bootstrap parser; it is additive only."""
    result = subprocess.run(
        [sys.executable, "-m", "che_core.designer", "bootstrap", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, "bootstrap --help must still exit 0"
    assert "mode" in result.stdout, "bootstrap parser must still expose the `mode` argument"
    assert "slug" in result.stdout, "bootstrap parser must still expose the `slug` argument"


# @ac B-1 follow-up — init subcommand is registered on the CLI parser
def test_init_subcommand_registered() -> None:
    """`che designer init --help` must exit 0 and document the --sub-product flag."""
    result = subprocess.run(
        [sys.executable, "-m", "che_core.designer", "init", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, "init --help must exit 0"
    assert "--sub-product" in result.stdout, "init parser must expose --sub-product"


# @ac B-1 git status — porcelain output after init on a real git worktree
def test_init_git_status_porcelain(tmp_path: Path) -> None:
    """Init inside a git-initialised tmp_path; `git status --porcelain` lists exactly the two untracked paths."""
    from che_core.designer import run_init

    wt = tmp_path
    # Initialise an inline git repo so `git status --porcelain` works
    _git(wt, "init", "-q")
    _git(wt, "config", "user.email", "ci@example.com")
    _git(wt, "config", "user.name", "CI")

    rc = run_init(str(wt), "sess-test-f0-b1-git", "acme")
    assert rc == 0

    result = _git(wt, "status", "--porcelain", "-uall")
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    # F0 + F3: init now writes BOTH the aggregating root (design/DESIGN.md + design/tokens/tokens.json)
    # AND sub-product-specific files (design/acme/DESIGN.md + design/acme/tokens/tokens.json).
    # R5 (sub-product isolation) demands paths are scoped under design/<sub_product>/.
    assert lines == [
        "?? design/DESIGN.md",
        "?? design/acme/DESIGN.md",
        "?? design/acme/tokens/tokens.json",
        "?? design/tokens/tokens.json",
    ], f"git status --porcelain -uall must list exactly the 4 untracked design paths; got {lines!r}"
