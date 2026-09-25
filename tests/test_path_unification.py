"""Path unification + state relocation (flat layout).

Guards the exact regression this increment exists to kill: the decisions log and
the worktree artifacts used to be computed by two different formulas, so a
worktree's history and its artifacts silently landed in different trees. Every
test here fails if those formulas ever diverge again.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from che_core.decisions import append_decision_jsonl, get_decisions_path
from che_core.diagnostics import CheError
from che_core.paths import compute_paths
from che_core.project_layout import get_state_registry_path
from che_core.registry import get_registry_path
from che_core.worktrees import add_worktree
from tests.conftest import bind_worktree

REPO_ROOT = Path(__file__).resolve().parents[1]


def _cli(*args: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run the Che CLI as a real subprocess, isolated to the current storage root."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [sys.executable, "-m", "che_core.cli", *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
        env=env,
    )


# --- B-4 ---------------------------------------------------------------------


def test_compute_paths_is_identical_regardless_of_cwd(bound_worktree, tmp_path: Path):
    # @ac B-4
    repo, expected = bind_worktree(tmp_path)

    for cwd in ("/", str(tmp_path), str(repo)):
        from_cwd = compute_paths(str(repo), "sess-1", cwd_override=cwd)
        assert from_cwd["CHE_WORKTREE_DIR"] == expected["CHE_WORKTREE_DIR"]
        assert from_cwd["CHE_PROJECT_SLUG"] == expected["CHE_PROJECT_SLUG"]


def test_compute_paths_ignores_ambient_process_cwd(bound_worktree, tmp_path: Path, monkeypatch):
    # @ac B-4 — resolution must be argument-driven, never os.getcwd()-driven.
    repo, expected = bind_worktree(tmp_path)

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    assert compute_paths(str(repo), "sess-1")["CHE_WORKTREE_DIR"] == expected["CHE_WORKTREE_DIR"]


def test_compute_paths_refuses_an_unbound_path(che_ws_root: Path, tmp_path: Path):
    # @ac B-4 — an unbound checkout must fail loudly instead of guessing a project.
    from tests.conftest import make_git_repo

    repo = make_git_repo(tmp_path / "unbound")

    with pytest.raises(CheError) as exc:
        compute_paths(str(repo), "sess-1")
    assert exc.value.code == "UNBOUND_WORKTREE"
    assert exc.value.exit_code == 3


# --- Git probes must be hermetic ---------------------------------------------


def test_git_probes_ignore_ambient_git_dir(che_ws_root: Path, tmp_path: Path, monkeypatch):
    """`is_git_repo` must answer about the path it was given, not about the caller.

    Regression: git exports GIT_DIR/GIT_INDEX_FILE to its hook subprocesses, and
    git hooks are exactly where Che runs (`pre-commit` / `pre-push` run pytest).
    An inherited GIT_DIR made `git -C <plain-dir> rev-parse` report the OUTER
    repository, so `che worktree add` accepted a non-repo path and wrote a
    binding pointing at nothing.
    """
    from che_core.project_layout import git_branch, git_origin, is_git_repo

    outer_repo, _ = bind_worktree(tmp_path)  # a real repo, so GIT_DIR has something to leak

    plain = tmp_path / "plain"
    plain.mkdir()

    monkeypatch.setenv("GIT_DIR", str(outer_repo / ".git"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(outer_repo / ".git" / "index"))

    assert is_git_repo(str(plain)) is False
    assert is_git_repo(str(outer_repo)) is True
    # The probes must also describe the *named* repo, not the ambient one.
    assert git_branch(str(plain)) is None
    assert git_origin(str(plain)) is None


def test_compute_paths_accepts_explicit_project_and_worktree(che_ws_root: Path, tmp_path: Path):
    # @ac B-4 — explicit arguments win, so a path need not be pre-bound yet.
    from che_core.workspaces import init_project
    from tests.conftest import make_git_repo

    repo = make_git_repo(tmp_path / "acme")
    init_project(str(repo), slug="acme")

    paths = compute_paths(str(repo), "sess-1", project_slug="acme", worktree_name="feature-x")
    assert paths["CHE_PROJECT_SLUG"] == "acme"
    assert paths["CHE_WORKTREE_NAME"] == "feature-x"
    assert paths["CHE_WORKTREE_DIR"] == str(che_ws_root / "acme" / "worktrees" / "feature-x")


# --- B-5 ---------------------------------------------------------------------


def test_decisions_and_artifacts_share_the_same_tree(bound_worktree, tmp_path: Path):
    # @ac B-5
    repo, paths = bind_worktree(tmp_path)
    worktree_dir = paths["CHE_WORKTREE_DIR"]

    decisions = get_decisions_path(str(repo))
    assert decisions == Path(worktree_dir) / "decisions.log.jsonl"

    append_decision_jsonl(str(repo), "SPEC", json.dumps({"k": "v"}))

    os.environ["CHE_WORKSPACE_SHARED"] = worktree_dir
    os.environ["WORKTREE_ROOT"] = str(repo)
    artifact = _cli("output_path", "spec", "myspec", "NONE", "workspace", "md")
    assert artifact.returncode == 0, artifact.stderr
    artifact_path = Path(artifact.stdout.strip())

    # The whole point: both live under the SAME worktree folder.
    assert artifact_path.is_relative_to(Path(worktree_dir)), artifact_path
    assert decisions.is_relative_to(Path(worktree_dir)), decisions


def test_decisions_path_no_longer_uses_the_legacy_wt_formula(bound_worktree, tmp_path: Path, che_ws_root):
    # @ac B-5 — regression lock for the duplicated `.wt/` formula.
    repo, _ = bind_worktree(tmp_path)
    decisions = get_decisions_path(str(repo))

    assert ".wt" not in decisions.parts, decisions
    assert decisions.parts[: len(che_ws_root.parts)] == che_ws_root.parts


# --- B-6 ---------------------------------------------------------------------


def test_registry_lives_in_the_workspace_root_not_the_source_package(che_ws_root: Path):
    # @ac B-6
    registry = get_registry_path()
    assert registry == get_state_registry_path()
    assert registry == che_ws_root / ".state" / "registry.jsonl"
    assert registry.is_relative_to(che_ws_root)
    # The harness source package must never hold user state.
    assert not registry.is_relative_to(REPO_ROOT.resolve())


def test_registry_append_creates_the_state_dir(che_ws_root: Path):
    # @ac B-6
    from che_core.registry import registry_append_jsonl

    registry_append_jsonl("sess-b6", "BOUND", "/tmp/some-repo", json.dumps({"workspace_name": "acme"}))
    registry = che_ws_root / ".state" / "registry.jsonl"
    assert registry.is_file()
    entry = json.loads(registry.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert entry["session_id"] == "sess-b6"
    assert entry["status"] == "BOUND"


# --- B-7 ---------------------------------------------------------------------

CONCURRENT_WRITERS = 200
MAX_PARALLEL = 16


def test_concurrent_appends_produce_only_valid_jsonl_lines(bound_worktree, tmp_path: Path):
    # @ac B-7
    repo, paths = bind_worktree(tmp_path)
    log = Path(paths["CHE_WORKTREE_DIR"]) / "decisions.log.jsonl"

    def write_one(index: int) -> int:
        return _cli(
            "decision_append",
            str(repo),
            "CONCURRENT",
            json.dumps({"i": index}),
        ).returncode

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
        codes = list(pool.map(write_one, range(CONCURRENT_WRITERS)))

    assert all(code == 0 for code in codes), f"non-zero exits: {[c for c in codes if c != 0]}"

    lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == CONCURRENT_WRITERS
    for ln in lines:
        json.loads(ln)  # every line must be complete and parseable


# --- AB-3 --------------------------------------------------------------------


def test_oversized_decision_payload_is_refused_without_corrupting_the_log(bound_worktree, tmp_path: Path):
    # @ac AB-3
    repo, paths = bind_worktree(tmp_path)
    log = Path(paths["CHE_WORKTREE_DIR"]) / "decisions.log.jsonl"

    append_decision_jsonl(str(repo), "SPEC", json.dumps({"ok": True}))
    before = log.read_text(encoding="utf-8")
    assert len(before.strip().splitlines()) == 1

    oversized = json.dumps({"blob": "X" * 9000})
    result = _cli("decision_append", str(repo), "SPEC", oversized)

    assert result.returncode != 0
    assert log.read_text(encoding="utf-8") == before
    assert len(log.read_text(encoding="utf-8").strip().splitlines()) == 1


# --- worktree reuse (B-2 companion, at the module level) ---------------------


def test_readding_a_worktree_reuses_the_existing_tree(bound_worktree, tmp_path: Path):
    # @ac B-2
    repo, paths = bind_worktree(tmp_path)
    # Che creates artifact folders lazily, so the seed makes its own — a fixture
    # must not depend on production code having pre-created it.
    specs_dir = Path(paths["CHE_WORKTREE_DIR"]) / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    (specs_dir / "keep.md").write_text("keep me\n", encoding="utf-8")

    result = add_worktree("acme", str(repo), "main")

    assert result["reused"] is True
    assert result["added"] is False
    assert (specs_dir / "keep.md").read_text(encoding="utf-8") == "keep me\n"


def test_list_projects_skips_legacy_workspace_leftovers(che_ws_root: Path):
    """Pre-flattening leftovers must never be misreported as flat projects."""
    from che_core.workspaces import list_projects

    legacy = che_ws_root / "old-workspace"
    (legacy / "some-project" / "project").mkdir(parents=True)
    (legacy / "some-worktree" / ".wt").mkdir(parents=True)

    result = list_projects()

    assert "old-workspace" not in [p.get("slug") for p in result]
    legacy_entry = next(p for p in result if "legacy_untouched" in p)
    assert "old-workspace" in legacy_entry["legacy_untouched"]


def test_unbound_lookup_survives_legacy_and_invalid_slug_folders(che_ws_root: Path, tmp_path: Path):
    """Path resolution must not crash on leftovers a user has not migrated yet.

    Regression: iterating the storage root used to attempt slug validation on every
    folder, so a legacy workspace named `Flockr` (uppercase, invalid slug) made every
    single `compute_paths` call raise instead of reporting "not bound".
    """
    from tests.conftest import make_git_repo

    (che_ws_root / "Flockr" / "some-worktree" / ".wt").mkdir(parents=True)
    (che_ws_root / "workspaces" / "acme" / "acme" / "project").mkdir(parents=True)

    repo = make_git_repo(tmp_path / "unbound")

    with pytest.raises(CheError) as exc:
        compute_paths(str(repo), "sess-1")
    assert exc.value.code == "UNBOUND_WORKTREE"
    assert exc.value.exit_code == 3
