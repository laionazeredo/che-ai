from pathlib import Path

import pytest

from che_core.diagnostics import CheError
from che_core.paths import (
    _slugify,
    assert_outside_worktree,
    output_path,
    resolve_worktree_slug,
    write_file_atomic,
)
from che_core.project_layout import get_state_registry_path


def test_slugify_basic():
    assert _slugify("Manifesto 48 Projetos") == "Manifesto-48-Projetos"
    assert _slugify("feat/FLO-513/process refund") == "feat--FLO-513--process-refund"
    assert _slugify("vc-educar/corp-website") == "vc-educar--corp-website"
    assert _slugify("main") == "main"
    assert _slugify("---test---") == "test"
    assert _slugify("a___b") == "a___b"  # Allows underscores


def test_resolve_worktree_slug(tmp_path, monkeypatch):
    """Test standard repo resolution"""
    # Create a mock git repo structure
    repo_dir = tmp_path / "my-repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()

    # Hermetic: git exports GIT_DIR/GIT_WORK_TREE to hooks, which would otherwise
    # leak the real repository into the subprocess and defeat the fallback tested here.
    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)

    # We mock the git branch resolution since we can't easily mock subprocess here
    # without pytest-mock, but we can test the fallback

    slug = resolve_worktree_slug(str(repo_dir))
    # It should fallback to main if git fails/is not mocked
    assert slug == "my-repo__main"


def test_resolve_worktree_slug_worktrees(tmp_path):
    """Test git worktree structure resolution"""
    worktrees_dir = tmp_path / "my-repo.worktrees"
    worktrees_dir.mkdir()

    feature_dir = worktrees_dir / "feat-FLO-513"
    feature_dir.mkdir()

    slug = resolve_worktree_slug(str(feature_dir))
    assert slug == "my-repo__feat-FLO-513"


def test_assert_outside_worktree_allows_outside(tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()
    outside = tmp_path / "shared" / "tasks" / "x.md"
    assert_outside_worktree(str(outside), str(wt), "TEST")  # no exception, no exit


def test_assert_outside_worktree_is_noop_on_empty(tmp_path):
    assert_outside_worktree("", str(tmp_path), "TEST")
    assert_outside_worktree("/tmp/whatever", "", "TEST")


def test_assert_outside_worktree_blocks_inside(tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()
    with pytest.raises(CheError) as exc:
        assert_outside_worktree(str(wt / ".che" / "leak.md"), str(wt), "TEST")
    assert exc.value.code == "STORAGE_BOUNDARY_VIOLATION"
    assert exc.value.exit_code == 99


def test_assert_outside_worktree_blocks_root_itself(tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()
    with pytest.raises(CheError) as exc:
        assert_outside_worktree(str(wt), str(wt), "TEST")
    assert exc.value.code == "STORAGE_BOUNDARY_VIOLATION"
    assert exc.value.exit_code == 99


def test_compute_paths_exposes_decisions_and_registry(bound_worktree):
    _repo, paths = bound_worktree

    # New keys replacing the orphan bash helpers che_decisions_path / che_registry_path.
    # The worktree folder itself is the shared/tactical area (legacy alias).
    assert paths["CHE_WORKSPACE_SHARED"] == paths["CHE_WORKTREE_DIR"]
    assert paths["CHE_DECISIONS_PATH"] == str(Path(paths["CHE_WORKSPACE_SHARED"]) / "decisions.log.jsonl")
    assert paths["CHE_REGISTRY_PATH"] == str(get_state_registry_path())
    assert paths["CHE_REGISTRY_PATH"] == str(Path(paths["CHE_STATE_DIR"]) / "registry.jsonl")
    # Reused existing key (replaces che_level2_binding_path).
    assert paths["CHE_LEVEL2_BINDING"] == str(Path(paths["CHE_SESSION_DIR"]) / "binding.md")


def test_output_path_session_scope(tmp_path, monkeypatch):
    session_dir = tmp_path / "session"
    monkeypatch.setenv("CHE_SESSION_DIR", str(session_dir))
    monkeypatch.delenv("WORKTREE_ROOT", raising=False)

    p = output_path("qa", "manual-test-plan", "FLO-123", "session", "md")
    assert p.startswith(str(session_dir / "qa" / "evidence" / "FLO-123"))
    assert p.endswith("-manual-test-plan.md")
    assert (session_dir / "qa" / "evidence" / "FLO-123").is_dir()


def test_output_path_workspace_scope_with_suffix(tmp_path, monkeypatch):
    shared = tmp_path / "shared"
    monkeypatch.setenv("CHE_WORKSPACE_SHARED", str(shared))

    p = output_path("task", "task-graph", "FLO-123", "workspace", "md", suffix="v2")
    assert p.startswith(str(shared / "tasks" / "FLO-123"))
    assert p.endswith("-task-graph_v2.md")


def test_output_path_maps_unknown_type_to_itself(tmp_path, monkeypatch):
    shared = tmp_path / "shared"
    monkeypatch.setenv("CHE_WORKSPACE_SHARED", str(shared))

    p = output_path("custom_kind", "artifact", "", "workspace", "json")
    assert p.startswith(str(shared / "custom_kind"))


def test_spec_lands_in_specs_folder_grouped_by_slug(tmp_path, monkeypatch):
    """The SPEC's one canonical home: `specs/<slug>/<ts>-spec.md`.

    `/che-spec` used to resolve this path and then ignore it, writing
    `$CHE_WORKSPACE_SHARED/spec_<slug>.md` at the root instead — while `/che-act`
    and `/che-ship` looked for the SPEC where `che-act` documents it (`specs/`).
    Writer and reader disagreed, so a fresh SPEC could be invisible to the gate.
    This pins the resolution both sides must agree on.
    """
    shared = tmp_path / "shared"
    monkeypatch.setenv("CHE_WORKSPACE_SHARED", str(shared))
    monkeypatch.delenv("WORKTREE_ROOT", raising=False)

    p = output_path("spec", "spec", "my-feature", "workspace", "md")

    assert Path(p).parent == shared / "specs" / "my-feature"
    assert Path(p).name.endswith("-spec.md")
    assert not (shared / "spec_my-feature.md").exists(), "the legacy root path must never be the target"


def test_output_path_rejects_bad_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("CHE_WORKSPACE_SHARED", str(tmp_path))
    with pytest.raises(CheError) as exc:
        output_path("qa", "x", "", "global", "md")
    assert exc.value.code == "INVALID_ARTIFACT_SCOPE"
    assert exc.value.exit_code == 2


def test_output_path_refuses_target_inside_worktree(tmp_path, monkeypatch):
    wt = tmp_path / "wt"
    wt.mkdir()
    monkeypatch.setenv("CHE_WORKSPACE_SHARED", str(wt / "nested"))
    with pytest.raises(CheError) as exc:
        output_path("task", "graph", "FLO-1", "workspace", "md", worktree_root=str(wt))
    assert exc.value.code == "STORAGE_BOUNDARY_VIOLATION"
    assert exc.value.exit_code == 99


def test_write_file_atomic_writes_content(tmp_path):
    target = tmp_path / "out" / "note.md"
    result = write_file_atomic(str(target), b"hello atomic")
    assert result == str(target)
    assert target.read_bytes() == b"hello atomic"
    assert not list((tmp_path / "out").glob("*.tmp.*"))


def test_write_file_atomic_refuses_inside_worktree(tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()
    with pytest.raises(CheError) as exc:
        write_file_atomic(str(wt / "leak.md"), b"x", worktree_root=str(wt))
    assert exc.value.code == "STORAGE_BOUNDARY_VIOLATION"
    assert exc.value.exit_code == 99
    assert not (wt / "leak.md").exists()


def test_write_file_atomic_requires_target():
    with pytest.raises(CheError) as exc:
        write_file_atomic("", b"x")
    assert exc.value.code == "MISSING_ARTIFACT_ARGUMENT"
