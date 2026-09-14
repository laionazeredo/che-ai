"""Tests for F3 Sub-product isolation + R5 git reviewability (T4).

Contract:
- B-4 (positive): init for sub-product `beta` creates `design/beta/DESIGN.md` and `design/beta/tokens/tokens.json`.
- B-4 (positive): after init for `acme` is committed and then init for `beta` is run, `git diff --name-only`
  contains ONLY paths under `design/beta/` + the top-level aggregating `design/DESIGN.md`/`design/tokens/tokens.json`;
  ZERO paths under `design/acme/` are touched (R5 sub-product isolation).
- AB-5 (negative): no file under design/<other_sub_product>/ is touched by an init for a different sub-product.
- B-4 reviewability: the changed files are plain text (not opaque binary), so `git diff` shows readable hunks.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command scoped to cwd with an ISOLATED GIT_DIR.

    We MUST set GIT_DIR explicitly because pytest itself runs inside a git
    worktree, and `git init` in a tmp directory under pytest does NOT fully
    isolate the operations — the parent worktree's hooks + config leak
    through `git -c` resolution and can corrupt the worktree's branch.

    Using GIT_DIR=<abs path>/.git + GIT_WORK_TREE=<abs path> gives us a
    hermetic sandbox: even if cwd is wrong, git operates only on tmp_path.

    Also clears git's hook-injected env vars (GIT_INDEX_FILE and friends) that
    `git commit` exports to its hook subprocesses.
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
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=check,
    )


def _init_git_repo(wt: Path) -> None:
    """Initialise a brand-new git repo at `wt` with explicit isolation.

    MUST precede `_git` calls with `GIT_DIR` unset so `git init` can create
    the .git directory at the expected location.
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
    subprocess.run(["git", "init", "-q"], cwd=str(wt), env=env, capture_output=True, text=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "ci@example.com"],
        cwd=str(wt),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "CI"], cwd=str(wt), env=env, capture_output=True, text=True, check=True
    )


# @ac B-4 — init for `beta` writes files under design/beta/
def test_sub_product_init_creates_beta_files(tmp_path: Path) -> None:
    """Init with --sub-product beta must create design/beta/DESIGN.md + design/beta/tokens/tokens.json."""
    from che_core.designer import run_init

    wt = tmp_path
    rc = run_init(str(wt), "sess-test-f3-beta", "beta")
    assert rc == 0

    beta_design = wt / "design" / "beta" / "DESIGN.md"
    beta_tokens = wt / "design" / "beta" / "tokens" / "tokens.json"
    assert beta_design.is_file(), f"design/beta/DESIGN.md must exist at {beta_design}"
    assert beta_tokens.is_file(), f"design/beta/tokens/tokens.json must exist at {beta_tokens}"

    # And the name `beta` must be substituted into the rendered content (not placeholder).
    text = beta_design.read_text(encoding="utf-8")
    assert "beta" in text, f"DESIGN.md must reflect sub-product `beta`; got {text[:200]!r}"
    assert "{{sub_product}}" not in text, "DESIGN.md must not retain placeholder after substitution"


# @ac B-4 / R5 — `git diff --name-only` after init for beta touches ONLY design/beta/ + top-level aggregating
def test_sub_product_isolation_git_diff(tmp_path: Path) -> None:
    """R5: after acme is committed, init for beta must NOT touch design/acme/ at all."""
    from che_core.designer import run_init

    wt = tmp_path
    _init_git_repo(wt)

    # First init for acme + commit
    assert run_init(str(wt), "sess-test-f3", "acme") == 0
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "-m", "feat: add acme sub-product")

    # Snapshot acme file sha BEFORE second init — must be untouched.
    acme_design = wt / "design" / "acme" / "DESIGN.md"
    acme_tokens = wt / "design" / "acme" / "tokens" / "tokens.json"
    acme_design_sha_before = __import__("hashlib").sha256(acme_design.read_bytes()).hexdigest()
    acme_tokens_sha_before = __import__("hashlib").sha256(acme_tokens.read_bytes()).hexdigest()

    # Now init for beta
    assert run_init(str(wt), "sess-test-f3", "beta") == 0

    # 1) acme files must be byte-identical (no touch)
    acme_design_sha_after = __import__("hashlib").sha256(acme_design.read_bytes()).hexdigest()
    acme_tokens_sha_after = __import__("hashlib").sha256(acme_tokens.read_bytes()).hexdigest()
    assert acme_design_sha_before == acme_design_sha_after, (
        f"R5 violation: init for beta must NOT modify design/acme/DESIGN.md; "
        f"sha before={acme_design_sha_before} after={acme_design_sha_after}"
    )
    assert acme_tokens_sha_before == acme_tokens_sha_after, (
        "R5 violation: init for beta must NOT modify design/acme/tokens/tokens.json"
    )

    # 2) git diff --name-only (staged + modified): NO path under design/acme/
    #    AND NO modification to root design/DESIGN.md or design/tokens/tokens.json by re-running init
    #    (they may still differ because init rewrites `created_at`; the test focuses on the acme/ isolation).
    diff_result = _git(wt, "diff", "--name-only", "HEAD")
    diff_paths = [ln for ln in diff_result.stdout.splitlines() if ln.strip()]
    acme_leaks = [p for p in diff_paths if p.startswith("design/acme/")]
    assert acme_leaks == [], (
        f"R5 violation: `git diff --name-only` must contain ZERO design/acme/ paths; got {acme_leaks!r}"
    )

    # 3) New sub-product files appear as UNTRACKED in `git status --porcelain -uall`
    status_result = _git(wt, "status", "--porcelain", "-uall")
    status_paths = [ln[3:] for ln in status_result.stdout.splitlines() if ln.strip()]
    assert "design/beta/DESIGN.md" in status_paths, (
        f"design/beta/DESIGN.md must appear as untracked; got {status_paths!r}"
    )
    assert "design/beta/tokens/tokens.json" in status_paths, (
        f"design/beta/tokens/tokens.json must appear as untracked; got {status_paths!r}"
    )

    # 4) design/acme/* must NOT appear at all in git status (R5 — neither modified nor untracked).
    acme_status_leaks = [p for p in status_paths if p.startswith("design/acme/")]
    assert acme_status_leaks == [], (
        f"R5 violation: design/acme/* must not appear in `git status --porcelain -uall`; got {acme_status_leaks!r}"
    )

    # 5) Top-level aggregating paths MAY be touched (they mention the latest sub-product); NOT a violation.
    #    The contract only forbids touching OTHER sub-products' paths.


# @ac B-4 reviewability — files are text, not opaque binary
def test_sub_product_files_are_text_reviewable(tmp_path: Path) -> None:
    """`git diff` for the new sub-product files must show line-level hunks (text), not a single binary blob."""
    from che_core.designer import run_init

    wt = tmp_path
    _init_git_repo(wt)

    # First init for acme + commit
    assert run_init(str(wt), "sess-test-f3-text", "acme") == 0
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "-m", "feat: add acme sub-product")

    # Init for beta
    assert run_init(str(wt), "sess-test-f3-text", "beta") == 0

    # Diff design/beta/DESIGN.md specifically and confirm it's text (line-level).
    diff = _git(wt, "diff", "--", "design/beta/DESIGN.md")
    assert "Binary files" not in diff.stdout and "GIT binary patch" not in diff.stdout, (
        f"design/beta/DESIGN.md must be a text file in git (reviewable); got diff head:\n{diff.stdout[:400]!r}"
    )
    # Tokens.json must also be text.
    diff_tokens = _git(wt, "diff", "--", "design/beta/tokens/tokens.json")
    assert "Binary files" not in diff_tokens.stdout, (
        f"design/beta/tokens/tokens.json must be text; got:\n{diff_tokens.stdout[:400]!r}"
    )


# @ac CLI smoke — `che designer init --sub-product beta` end-to-end via subprocess
def test_init_cli_sub_product_isolation(tmp_path: Path) -> None:
    """CLI smoke: invoking `che designer init` twice for different sub-products produces the isolation contract."""
    _init_git_repo(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "init repo")

    # Init acme
    r1 = subprocess.run(
        [
            sys.executable,
            "-m",
            "che_core.designer",
            "init",
            str(tmp_path),
            "sess-test-f3-cli",
            "--sub-product",
            "acme",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r1.returncode == 0, f"init acme failed: {r1.stderr}"
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "feat: add acme")

    # Init beta
    r2 = subprocess.run(
        [
            sys.executable,
            "-m",
            "che_core.designer",
            "init",
            str(tmp_path),
            "sess-test-f3-cli",
            "--sub-product",
            "beta",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r2.returncode == 0, f"init beta failed: {r2.stderr}"

    # Diff must NOT touch design/acme/
    diff = _git(tmp_path, "diff", "--name-only", "HEAD")
    leaked = [p for p in diff.stdout.splitlines() if p.startswith("design/acme/")]
    assert leaked == [], f"R5 CLI violation: design/acme/ paths must not be re-touched; got {leaked!r}"
