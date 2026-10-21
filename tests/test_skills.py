"""Skill discovery — project > repository > global, resolved deterministically."""

import os
from pathlib import Path

import pytest

from che_core.diagnostics import CheError
from che_core.skills import list_skills, parse_frontmatter


def write_skill(directory: Path, name: str, description: str) -> Path:
    """Create ``<directory>/<name>/SKILL.md`` with the canonical frontmatter."""
    skill_dir = directory / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    return skill_file


def test_frontmatter_reads_quoted_values():
    text = '---\nname: "alpha"\ndescription: "Does a thing."\n---\n\n# Alpha\n'
    assert parse_frontmatter(text) == {"name": "alpha", "description": "Does a thing."}


def test_frontmatter_joins_folded_description():
    text = "---\nname: alpha\ndescription: >\n  First line\n  second line.\n---\n"
    assert parse_frontmatter(text)["description"] == "First line second line."


def test_frontmatter_absent_returns_empty_mapping():
    assert parse_frontmatter("# No frontmatter\n") == {}


def test_project_skill_shadows_global_skill(bound_worktree, tmp_path, monkeypatch):
    repo, _ = bound_worktree
    root = Path(os.environ["CHE_WORKSPACES_ROOT"])
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))

    project_skill = write_skill(root / "acme" / "skills", "deploy", "Project deploy.")
    global_skill = write_skill(home / ".claude" / "skills", "deploy", "Generic deploy.")
    write_skill(home / ".claude" / "skills", "che-act", "Orchestrate.")

    result = list_skills(project="acme", repo=str(repo))

    assert result["project_slug"] == "acme"
    assert [s["name"] for s in result["skills"]] == ["deploy", "che-act"]
    effective = result["skills"][0]
    assert effective["scope"] == "project"
    assert effective["path"] == str(project_skill)
    assert effective["description"] == "Project deploy."
    assert result["shadowed"] == [
        {
            "name": "deploy",
            "description": "Generic deploy.",
            "scope": "global",
            "path": str(global_skill),
            "shadowed_by": "project",
        }
    ]


def test_repository_skill_sits_between_project_and_global(bound_worktree, tmp_path, monkeypatch):
    repo, _ = bound_worktree
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    write_skill(repo / ".claude" / "skills", "review", "Repo review.")

    result = list_skills(project="acme", repo=str(repo))

    assert [(s["name"], s["scope"]) for s in result["skills"]] == [("review", "repository")]


def test_project_slug_is_resolved_from_the_bound_worktree(bound_worktree, tmp_path, monkeypatch):
    repo, _ = bound_worktree
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    root = Path(os.environ["CHE_WORKSPACES_ROOT"])
    write_skill(root / "acme" / "skills", "deploy", "Project deploy.")

    result = list_skills(repo=str(repo))

    assert result["project_slug"] == "acme"
    assert result["skills"][0]["name"] == "deploy"


def test_project_is_resolved_from_the_init_registry_without_a_worktree(tmp_path, monkeypatch):
    root = tmp_path / "che-workspaces"
    monkeypatch.setenv("CHE_WORKSPACES_ROOT", str(root))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = tmp_path / "repo"
    repo.mkdir()
    (root / "acme").mkdir(parents=True)
    (root / "acme" / "registry.jsonl").write_text(
        f'{{"event": "PROJECT_INIT", "project_slug": "acme", "repo_root": "{repo}"}}\n',
        encoding="utf-8",
    )
    write_skill(root / "acme" / "skills", "deploy", "Project deploy.")

    result = list_skills(repo=str(repo))

    assert result["project_slug"] == "acme"
    assert [(s["name"], s["scope"]) for s in result["skills"]] == [("deploy", "project")]


def test_unbound_repo_lists_repository_and_global_scopes_only(tmp_path, monkeypatch):
    monkeypatch.setenv("CHE_WORKSPACES_ROOT", str(tmp_path / "che-workspaces"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = tmp_path / "unbound"
    repo.mkdir()
    write_skill(repo / ".trae" / "skills", "local", "Repo local.")

    result = list_skills(repo=str(repo))

    assert result["project_slug"] is None
    assert [(s["name"], s["scope"]) for s in result["skills"]] == [("local", "repository")]


def test_unknown_project_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setenv("CHE_WORKSPACES_ROOT", str(tmp_path / "che-workspaces"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    with pytest.raises(CheError) as exc_info:
        list_skills(project="ghost", repo=str(tmp_path))

    assert exc_info.value.code == "UNKNOWN_PROJECT"


def test_folder_without_skill_file_is_ignored(bound_worktree, tmp_path, monkeypatch):
    repo, _ = bound_worktree
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    root = Path(os.environ["CHE_WORKSPACES_ROOT"])
    (root / "acme" / "skills" / "empty").mkdir(parents=True)

    result = list_skills(project="acme", repo=str(repo))

    assert result["skills"] == []
