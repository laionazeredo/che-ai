"""A bound worktree is born with nothing but its binding.

SPEC `lean-worktree-layout`. Che creates artifact folders lazily — `output_path`
makes the parent of every artifact at write time — so no eager subfolder list may
exist. Every test here fails if someone reintroduces one.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from che_core.diagnostics import CheError
from che_core.paths import output_path
from che_core.ship import QUARANTINE_DIRNAME, run_blacklist_check
from che_core.worktrees import add_worktree
from tests.conftest import bind_worktree, isolated_git_env


def _entries(path: Path) -> list[str]:
    return sorted(p.name for p in path.iterdir())


def _tracked_leak(repo: Path, name: str = "spec_leak.md") -> Path:
    """Drop a blacklisted planning artifact into the repo AND commit it.

    Committing is what selects the refusal path: an untracked leak is moved to quarantine, a tracked
    one stops the run, because deleting a file that exists in git history is not ours to decide.
    """
    leak = repo / name
    leak.write_text("tracked planning artifact\n", encoding="utf-8")

    env = isolated_git_env()
    git = ["git", "-C", str(repo), "-c", "user.email=test@che.local", "-c", "user.name=Che Test"]
    subprocess.run([*git, "add", name], check=True, capture_output=True, env=env)
    subprocess.run([*git, "commit", "-q", "-m", "leak"], check=True, capture_output=True, env=env)
    return leak


# --- B-1 ----------------------------------------------------------------------


def test_new_worktree_has_no_subdirs(tmp_path: Path) -> None:
    # @ac B-1
    """A freshly bound worktree holds `.binding.json` and no directories.

    Covers BOTH eager sites at once: `bind_worktree` runs `add_worktree` and then
    `ensure_session_dirs`, which used to create the same folders independently.
    """
    _, paths = bind_worktree(tmp_path)
    wt_dir = Path(paths["CHE_WORKTREE_DIR"])

    assert _entries(wt_dir) == [".binding.json"]
    assert [p for p in wt_dir.iterdir() if p.is_dir()] == []


# --- B-2 ----------------------------------------------------------------------


def test_output_path_creates_parent_on_demand(tmp_path: Path, monkeypatch) -> None:
    # @ac B-2
    """`output_path` creates a missing artifact folder at write time."""
    shared = tmp_path / "shared"
    shared.mkdir()
    monkeypatch.setenv("CHE_WORKSPACE_SHARED", str(shared))
    monkeypatch.delenv("WORKTREE_ROOT", raising=False)

    assert not (shared / "specs").exists()

    resolved = output_path("spec", "spec", "", "workspace", "md")

    assert Path(resolved).parent == shared / "specs"
    assert (shared / "specs").is_dir()


# --- B-4 ----------------------------------------------------------------------


def test_gh_stack_type_maps_to_pr_plans(tmp_path: Path, monkeypatch) -> None:
    # @ac B-4
    """The `gh_stack` artifact type lands in `pr_plans/`, named for the artifact."""
    shared = tmp_path / "shared"
    shared.mkdir()
    monkeypatch.setenv("CHE_WORKSPACE_SHARED", str(shared))
    monkeypatch.delenv("WORKTREE_ROOT", raising=False)

    resolved = output_path("gh_stack", "gh-stack-plan", "", "workspace", "md")

    assert Path(resolved).parent == shared / "pr_plans"
    assert not (shared / "gh_stack").exists()


# --- B-3 / AB-2 ---------------------------------------------------------------


def test_blacklist_moves_to_quarantine(tmp_path: Path) -> None:
    # @ac B-3
    """An untracked planning artifact leaked into the repo is moved, not deleted."""
    repo, paths = bind_worktree(tmp_path)
    leak = Path(repo) / "spec_leak.md"
    leak.write_text("planning artifact\n", encoding="utf-8")

    run_blacklist_check(str(repo), "sess-lean")

    quarantined = Path(paths["CHE_WORKSPACE_SHARED"]) / QUARANTINE_DIRNAME / "spec_leak.md"
    assert quarantined.is_file(), "blacklisted artifact must land in the quarantine"
    assert quarantined.read_text(encoding="utf-8") == "planning artifact\n"
    assert not leak.exists(), "the leaked copy must no longer sit in the user repo"


def test_quarantine_never_deletes(tmp_path: Path) -> None:
    # @ac AB-2
    """A TRACKED artifact aborts the run and survives — never silently removed."""
    repo, _ = bind_worktree(tmp_path)
    leak = _tracked_leak(repo)

    with pytest.raises(CheError) as exc:
        run_blacklist_check(str(repo), "sess-lean")

    assert exc.value.code == "PLANNING_ARTIFACTS_TRACKED"
    assert exc.value.exit_code == 2, "a tracked artifact must stop the ship, not be moved"
    assert leak.is_file(), "a tracked artifact must never be silently deleted"
    assert leak.read_text(encoding="utf-8") == "tracked planning artifact\n"


def test_the_refusal_keeps_stdout_for_the_machine_channel(tmp_path: Path, capsys) -> None:
    """The A/B options are human guidance, so they belong on stderr.

    `--json` writes the failure envelope to stdout, and prose printed there first would leave the
    stream unparseable — worse than no JSON at all, because a caller cannot tell. Asserted directly
    rather than through `--json`, which the ship CLI does not accept: the invariant is what matters,
    not the flag that would exercise it.
    """
    repo, _ = bind_worktree(tmp_path)
    _tracked_leak(repo)

    with pytest.raises(CheError):
        run_blacklist_check(str(repo), "sess-lean")

    captured = capsys.readouterr()
    assert captured.out == "", "stdout is the machine channel and must stay empty here"
    assert "Options:" in captured.err
    assert "A = Untrack them" in captured.err


# --- AB-1 ---------------------------------------------------------------------


def test_idempotent_reuse_preserves_artifacts(tmp_path: Path) -> None:
    # @ac AB-1
    """Re-binding reuses the tree: nothing is destroyed and nothing reappears.

    This is the regression lock for removing the eager `mkdir`. If the lazy
    rewrite ever turned reuse into a recreate, the seeded `specs/keep.md` would
    vanish — and if the eager list came back, extra directories would show up.
    """
    repo, paths = bind_worktree(tmp_path)
    wt_dir = Path(paths["CHE_WORKTREE_DIR"])

    specs = wt_dir / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    (specs / "keep.md").write_text("keep me\n", encoding="utf-8")
    before = _entries(wt_dir)

    result = add_worktree("acme", str(repo), "main")

    assert result["reused"] is True
    assert result["added"] is False
    assert (specs / "keep.md").read_text(encoding="utf-8") == "keep me\n"
    assert _entries(wt_dir) == before
