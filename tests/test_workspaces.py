"""Tests for the flat project/worktree layout (Sep 2026 flattening).

The L1 "workspace" grouping level was retired: a project lives directly under
``CHE_WORKSPACES_ROOT`` and only a *worktree* binds a filesystem path. These tests
cover the new project lifecycle plus the CLI acceptance criteria.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from che_core.diagnostics import CheError
from che_core.hooks import posttooluse_git_worktree
from che_core.paths import _slugify, project_slug_from_git_origin, resolve_workspace_name, resolve_worktree_slug
from che_core.project_layout import DOMAIN_SLUGS, get_project_dir, get_trash_dir, get_workspaces_root
from che_core.workspaces import (
    cleanup_worktree_l3,
    ensure_worktree_l3_dirs,
    init_project,
    list_projects,
    list_trash,
    remove_project,
    restore_project,
)
from che_core.worktrees import add_worktree, find_worktree_by_path, list_worktrees, worktree_exists
from tests.conftest import isolated_git_env, make_git_repo

CHE_CLI_CMD = [sys.executable, "-m", "che_core.cli"]

PROJECT_DOCS = ("architecture.md", "project_profile.md", "product_context.md", "roadmap.md")


@pytest.fixture(autouse=True)
def _isolate_workspaces_root(tmp_path, monkeypatch) -> Path:
    """Pin CHE_WORKSPACES_ROOT to a tmp dir — never touch the real ~/.che-workspaces."""
    isolated = tmp_path / "che-ws-test"
    isolated.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CHE_WORKSPACES_ROOT", str(isolated))
    return isolated


def _run_cli(*args):
    """Runs the Che CLI and returns (exit_code, stdout, stderr)."""
    proc = subprocess.run(CHE_CLI_CMD + list(args), capture_output=True, text=True, env={**os.environ}, check=False)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _parse_json(s):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None


def _add_origin(repo: Path, url: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", url],
        check=True,
        capture_output=True,
        env=isolated_git_env(),
    )


# --- CLI acceptance criteria --------------------------------------------------


def test_cli_project_init_creates_flat_skeleton(tmp_path, _isolate_workspaces_root):
    # @ac B-1
    """`che project init <git-repo> --slug acme` → exit 0 and the flat skeleton + durable docs."""
    repo = make_git_repo(tmp_path / "repo")
    code, out, err = _run_cli("project", "init", str(repo), "--slug", "acme")
    assert code == 0, f"exit={code} stderr={err}"
    data = _parse_json(out)
    assert data["initialised"] is True

    project_dir = _isolate_workspaces_root / "acme"
    assert Path(data["project_dir"]) == project_dir
    for domain in DOMAIN_SLUGS:
        assert (project_dir / domain).is_dir(), f"missing domain folder: {domain}"
    assert (project_dir / "worktrees").is_dir()
    assert (project_dir / "_db").is_dir()
    for doc in PROJECT_DOCS:
        assert (project_dir / doc).is_file(), f"missing durable doc: {doc}"


def test_cli_worktree_add_reuses_existing_tree_on_second_run(tmp_path, _isolate_workspaces_root):
    # @ac B-2
    """`che worktree add` is idempotent: the second run reports reused=true and does not duplicate."""
    repo = make_git_repo(tmp_path / "repo")
    assert _run_cli("project", "init", str(repo), "--slug", "acme")[0] == 0

    code, out, err = _run_cli("worktree", "add", str(repo), "--project", "acme", "--name", "main")
    assert code == 0, f"exit={code} stderr={err}"
    first = _parse_json(out)
    assert first["added"] is True
    assert first["reused"] is False

    worktree_dir = _isolate_workspaces_root / "acme" / "worktrees" / "main"
    assert worktree_dir.is_dir()
    assert Path(first["worktree_dir"]) == worktree_dir

    code2, out2, err2 = _run_cli("worktree", "add", str(repo), "--project", "acme", "--name", "main")
    assert code2 == 0, f"exit={code2} stderr={err2}"
    second = _parse_json(out2)
    assert second["reused"] is True
    assert second["added"] is False
    assert Path(second["worktree_dir"]) == worktree_dir
    # The same tree was reused, not duplicated.
    assert sorted(p.name for p in worktree_dir.parent.iterdir()) == ["main"]


def test_cli_worktree_list_lists_bound_worktree_without_sessions_folder(tmp_path, _isolate_workspaces_root):
    # @ac B-3
    """`che worktree list --project acme` → exit 0, lists the binding, no sessions/ inside it."""
    repo = make_git_repo(tmp_path / "repo")
    assert _run_cli("project", "init", str(repo), "--slug", "acme")[0] == 0
    assert _run_cli("worktree", "add", str(repo), "--project", "acme", "--name", "main")[0] == 0

    code, out, err = _run_cli("worktree", "list", "--project", "acme")
    assert code == 0, f"exit={code} stderr={err}"
    listed = _parse_json(out)
    assert isinstance(listed, list)
    assert [w["name"] for w in listed] == ["main"]

    worktree_dir = Path(listed[0]["worktree_dir"])
    assert worktree_dir == _isolate_workspaces_root / "acme" / "worktrees" / "main"
    # Sessions live under <project>/.sessions/<id>, never inside the reusable worktree folder.
    assert not (worktree_dir / "sessions").exists()


def test_cli_worktree_add_refuses_non_git_path(tmp_path, _isolate_workspaces_root):
    # @ac AB-1
    """A non-git path is a usage error (exit 2) and must not create the worktree folder."""
    repo = make_git_repo(tmp_path / "repo")
    assert _run_cli("project", "init", str(repo), "--slug", "acme")[0] == 0

    not_a_repo = tmp_path / "not-a-git-repo"
    not_a_repo.mkdir()
    code, _out, err = _run_cli("worktree", "add", str(not_a_repo), "--project", "acme", "--name", "x")
    assert code == 2, f"expected usage exit 2, got {code}: {err}"
    assert not (_isolate_workspaces_root / "acme" / "worktrees" / "x").exists()


def test_cli_project_init_twice_preserves_edited_roadmap(tmp_path, _isolate_workspaces_root):
    # @ac AB-2
    """Re-running `che project init` must not rewrite an already-edited roadmap.md."""
    repo = make_git_repo(tmp_path / "repo")
    assert _run_cli("project", "init", str(repo), "--slug", "acme")[0] == 0

    roadmap = _isolate_workspaces_root / "acme" / "roadmap.md"
    edited = "# Roadmap — hand edited\n\nNow: ship the flat layout.\n"
    roadmap.write_text(edited, encoding="utf-8")

    assert _run_cli("project", "init", str(repo), "--slug", "acme")[0] == 0
    assert roadmap.read_text(encoding="utf-8") == edited


# --- Project lifecycle (in-process) -------------------------------------------


def test_init_project_refuses_non_git_path(tmp_path, _isolate_workspaces_root):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(CheError) as exc:
        init_project(str(plain), slug="acme")
    assert exc.value.code == "NOT_A_GIT_REPOSITORY"
    assert exc.value.exit_code == 2
    assert not (_isolate_workspaces_root / "acme").exists()


@pytest.mark.parametrize("bad_slug", ["", "   ", "Acme", "with space", "a" * 64])
def test_init_project_refuses_invalid_slug(tmp_path, bad_slug):
    repo = make_git_repo(tmp_path / "repo")
    with pytest.raises(CheError) as exc:
        init_project(str(repo), slug=bad_slug)
    assert exc.value.code == "INVALID_SLUG"
    assert exc.value.exit_code == 2


def test_list_projects_reports_docs_domains_and_worktrees(tmp_path, _isolate_workspaces_root):
    repo = make_git_repo(tmp_path / "repo")
    init_project(str(repo), slug="acme")
    add_worktree("acme", str(repo), "main")

    projects = list_projects()
    assert len(projects) == 1
    entry = projects[0]
    assert entry["slug"] == "acme"
    assert Path(entry["path"]) == _isolate_workspaces_root / "acme"
    assert entry["architecture_exists"] is True
    assert entry["project_profile_exists"] is True
    assert entry["worktrees"] == ["main"]
    assert set(entry["domains"]) == set(DOMAIN_SLUGS)
    assert "README.txt" in entry["db_files"]


def test_remove_project_is_dry_run_by_default_then_trashes_with_manifest(tmp_path):
    repo = make_git_repo(tmp_path / "repo")
    init_project(str(repo), slug="acme")
    project_dir = get_project_dir("acme")

    plan = remove_project("acme")
    assert plan["dry_run"] is True
    assert plan["applied"] is False
    assert project_dir.is_dir()

    # Applying without --confirm is refused (usage exit 2) and changes nothing.
    with pytest.raises(CheError) as exc:
        remove_project("acme", dry_run=False, confirmed=False)
    assert exc.value.code == "REFUSED_WITHOUT_CONFIRM"
    assert exc.value.exit_code == 2
    assert project_dir.is_dir()

    applied = remove_project("acme", dry_run=False, confirmed=True)
    assert applied["applied"] is True
    assert not project_dir.exists()

    trash_path = Path(applied["trash_path"])
    assert trash_path.is_dir()
    assert trash_path.parent == get_trash_dir()
    manifest = json.loads((trash_path / "_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["kind"] == "project"
    assert manifest["original_path"] == str(project_dir)
    assert any(entry["slug"] == applied["trash_slug"] for entry in list_trash())


def test_restore_project_moves_the_flat_folder_back(tmp_path):
    repo = make_git_repo(tmp_path / "repo")
    init_project(str(repo), slug="acme")
    project_dir = get_project_dir("acme")
    (project_dir / "roadmap.md").write_text("edited roadmap\n", encoding="utf-8")

    moved = remove_project("acme", dry_run=False, confirmed=True)
    assert not project_dir.exists()

    result = restore_project(moved["trash_slug"])
    assert result["restored"] is True
    assert Path(result["restored_to"]) == project_dir
    assert (project_dir / "roadmap.md").read_text(encoding="utf-8") == "edited roadmap\n"


def test_restore_project_refuses_to_overwrite_existing_target(tmp_path):
    repo = make_git_repo(tmp_path / "repo")
    init_project(str(repo), slug="acme")
    moved = remove_project("acme", dry_run=False, confirmed=True)

    init_project(str(repo), slug="acme")  # recreates the target folder -> conflict
    with pytest.raises(CheError) as exc:
        restore_project(moved["trash_slug"])
    assert exc.value.code == "RESTORE_TARGET_EXISTS"
    assert exc.value.exit_code == 3
    # The trashed copy is left untouched.
    assert (Path(moved["trash_path"]) / "_MANIFEST.json").is_file()


# --- Hook helpers -------------------------------------------------------------


def test_ensure_worktree_l3_dirs_reports_unbound_note_without_guessing(tmp_path):
    repo = make_git_repo(tmp_path / "repo")
    _add_origin(repo, "git@github.com:acme/ghost.git")

    result = ensure_worktree_l3_dirs(str(repo))
    assert result["bound"] is False
    assert "che worktree add" in result["note"]
    # No project was guessed into existence.
    assert list(get_workspaces_root().glob("*/worktrees/*")) == []


def test_ensure_worktree_l3_dirs_binds_repo_whose_origin_matches_a_project(tmp_path):
    repo = make_git_repo(tmp_path / "repo")
    _add_origin(repo, "git@github.com:acme/repo.git")
    init_project(str(repo), slug="acme")

    result = ensure_worktree_l3_dirs(str(repo))
    assert result["bound"] is True
    assert result["project"] == "acme"
    assert result["worktree"] == "repo"
    assert worktree_exists("acme", "repo")


def test_hook_git_worktree_add_binds_a_matching_project(tmp_path):
    repo = make_git_repo(tmp_path / "repo")
    _add_origin(repo, "git@github.com:acme/repo.git")
    init_project(str(repo), slug="acme")

    payload = {"toolName": "RunCommand", "toolArgs": {"command": f"cd /tmp && git worktree add {repo} feat/x"}}
    result = posttooluse_git_worktree(payload)
    assert result["decision"] == "allow"
    assert "AUTO" in result["additionalContext"]
    assert [w["name"] for w in list_worktrees("acme")] == ["repo"]


def test_list_worktrees_skips_a_non_conforming_dir_name(tmp_path):
    """A legacy `<repo>__<branch>` folder must not take the whole CLI down.

    Such a folder cannot be a worktree (`get_worktree_dir` refuses the name), but
    `list_projects` and `find_worktree_by_path` both iterate through
    `list_worktrees`, so raising on it made `che project list` die with a
    traceback for the entire machine and left every path lookup in the project
    unresolvable.
    """
    repo = make_git_repo(tmp_path / "repo")
    init_project(str(repo), slug="acme")
    add_worktree("acme", str(repo), "main")

    legacy = get_project_dir("acme") / "worktrees" / "repo__feat-something"
    legacy.mkdir(parents=True)
    (legacy / ".binding.json").write_text("{}")

    assert [w["name"] for w in list_worktrees("acme")] == ["main"]
    assert [p["worktrees"] for p in list_projects()] == [["main"]]
    assert [m["name"] for m in find_worktree_by_path(str(repo))] == ["main"]


def test_cleanup_worktree_l3_reports_the_bound_worktree(tmp_path):
    repo = make_git_repo(tmp_path / "repo")
    init_project(str(repo), slug="acme")
    add_worktree("acme", str(repo), "main")

    result = cleanup_worktree_l3(str(repo))
    assert result["found"] == [{"project": "acme", "worktree": "main"}]


# --- Backward-compatible path helpers -----------------------------------------


def test_slugify_is_stable_for_legacy_paths():
    assert _slugify("Manifesto 48 Projetos") == "Manifesto-48-Projetos"
    assert _slugify("feat/FLO-513/process refund") == "feat--FLO-513--process-refund"
    assert _slugify("vc-educar/corp-website") == "vc-educar--corp-website"
    assert _slugify("") == ""


def test_resolve_worktree_slug_falls_back_to_main_branch(tmp_path, monkeypatch):
    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)
    repo = tmp_path / "my-repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    assert resolve_worktree_slug(str(repo)) == "my-repo__main"


def test_resolve_workspace_name_prefers_explicit_env_override(monkeypatch):
    monkeypatch.setenv("CHE_WORKSPACE_NAME_OVERRIDE", "explicit-ws")
    assert resolve_workspace_name("/tmp/whatever") == "explicit-ws"


def test_resolve_workspace_name_defaults_when_nothing_matches(tmp_path, monkeypatch):
    for var in (
        "CHE_WORKSPACE_NAME_OVERRIDE",
        "HARNESS_WORKSPACE_NAME_OVERRIDE",
        "CHE_WORKSPACE_NAME",
        "HARNESS_WORKSPACE_NAME",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CHE_CODE_WORKSPACES_DIR", str(tmp_path / "missing"))
    assert resolve_workspace_name(str(tmp_path)) == "default"


def test_project_slug_from_git_origin_derives_slug_from_remote(tmp_path, monkeypatch):
    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)
    repo = make_git_repo(tmp_path / "repo")
    _add_origin(repo, "git@github.com:acme/shop.git")
    assert project_slug_from_git_origin(str(repo)) == "acme-shop"
