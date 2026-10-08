"""Tests for the project knowledge engine: ``che knowledge scaffold`` / ``show`` / ``apply``.

The knowledge documents live under the project folder (never the user worktree), so the
tests drive a real bound project through the shared ``bound_worktree`` fixture.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from che_core.diagnostics import CheError
from che_core.knowledge import (
    CONVENTION_TOPICS,
    UNIVERSAL_SECTIONS,
    apply_ops,
    conventions_path,
    glossary_path,
    parse_glossary,
    parse_sections,
    parse_topics,
    render_conventions_skeleton,
    render_glossary,
    scaffold_conventions,
    show_knowledge,
)
from che_core.project_layout import get_workspaces_root

WORKTREE = Path(__file__).resolve().parents[1]


def _run_cli(root: Path, *argv: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "WORKTREE_ROOT"}
    env["CHE_WORKSPACES_ROOT"] = str(root)
    return subprocess.run(
        [sys.executable, "-m", "che_core.cli", *argv],
        cwd=str(WORKTREE),
        env=env,
        capture_output=True,
        text=True,
    )


def _root(bound_worktree) -> Path:
    return Path(bound_worktree[1]["CHE_PROJECT_DIR"]).parent


def _insert(term: str = "Envelope", definition: str = "A handoff contract") -> dict:
    return {"glossary": [{"op": "insert", "term": term, "definition": definition}]}


# --- T1 (F0): scaffold + show -----------------------------------------------------


def test_skeleton_contains_every_canonical_section():
    # @ac B-1
    text = render_conventions_skeleton("acme", "engineering")
    for index, title in enumerate(UNIVERSAL_SECTIONS, start=1):
        assert f"## {index}. {title}" in text


def test_skeleton_contains_the_domain_specific_authoring_topics():
    # @ac B-1
    text = render_conventions_skeleton("acme", "engineering")
    assert "### 5.1 Code Style" in text
    for topic in CONVENTION_TOPICS["engineering"]:
        assert topic in text


def test_skeleton_is_deterministic():
    assert render_conventions_skeleton("acme", "devops") == render_conventions_skeleton("acme", "devops")


def test_parse_sections_round_trips_the_skeleton():
    sections = parse_sections(render_conventions_skeleton("acme", "business"))
    assert list(sections) == [f"{i}. {t}" for i, t in enumerate(UNIVERSAL_SECTIONS, start=1)]


def test_parse_sections_rejects_a_duplicate_heading():
    with pytest.raises(AssertionError):
        parse_sections("## 1. Scope & Precedence\n\nbody\n\n## 1. Scope & Precedence\n\nagain\n")


def test_scaffold_creates_the_file_then_is_idempotent(bound_worktree, monkeypatch):
    # @ac B-1
    monkeypatch.delenv("WORKTREE_ROOT", raising=False)
    first = scaffold_conventions("acme", "engineering")
    path = conventions_path("acme", "engineering")
    assert first["created"] is True and path.is_file()
    before = path.read_bytes()

    second = scaffold_conventions("acme", "engineering")
    assert second["created"] is False
    assert path.read_bytes() == before


def test_show_returns_the_sections_of_a_scaffolded_domain(bound_worktree, monkeypatch):
    # @ac B-1
    monkeypatch.delenv("WORKTREE_ROOT", raising=False)
    scaffold_conventions("acme", "engineering")
    shown = show_knowledge("acme", "engineering")
    assert shown["exists"] is True
    assert len(shown["sections"]) == len(UNIVERSAL_SECTIONS)


def test_show_on_an_empty_project_returns_empty_without_creating_a_file(bound_worktree, monkeypatch):
    # @ac B-5
    monkeypatch.delenv("WORKTREE_ROOT", raising=False)
    shown = show_knowledge("acme", "devops")
    assert shown["exists"] is False and shown["sections"] == {}
    assert not conventions_path("acme", "devops").is_file()


def test_show_inventory_lists_only_domains_that_have_conventions(bound_worktree, monkeypatch):
    # @ac B-5
    monkeypatch.delenv("WORKTREE_ROOT", raising=False)
    assert show_knowledge("acme")["domains"] == []
    scaffold_conventions("acme", "product")
    assert [entry["domain"] for entry in show_knowledge("acme")["domains"]] == ["product"]


def test_unknown_domain_is_rejected(bound_worktree):
    with pytest.raises(CheError) as exc:
        scaffold_conventions("acme", "not-a-domain")
    assert exc.value.code == "INVALID_DOMAIN"


def test_unknown_project_is_rejected(che_ws_root):
    with pytest.raises(CheError) as exc:
        scaffold_conventions("ghost", "engineering")
    assert exc.value.code == "UNKNOWN_PROJECT"


def test_scaffold_refuses_a_target_inside_the_worktree(bound_worktree, monkeypatch):
    # @ac AB-3
    monkeypatch.setenv("WORKTREE_ROOT", str(get_workspaces_root()))
    with pytest.raises(CheError) as exc:
        scaffold_conventions("acme", "engineering")
    assert exc.value.code == "STORAGE_BOUNDARY_VIOLATION"


def test_cli_scaffold_then_show_end_to_end(bound_worktree):
    root = _root(bound_worktree)

    scaffold = _run_cli(root, "knowledge", "scaffold", "--project", "acme", "--domain", "engineering")
    assert scaffold.returncode == 0, scaffold.stderr

    shown = _run_cli(root, "knowledge", "show", "--project", "acme", "--domain", "engineering")
    assert shown.returncode == 0, shown.stderr
    assert "## 11. Gaps & Open Questions" in shown.stdout


def test_cli_rejects_an_unknown_domain(bound_worktree):
    root = _root(bound_worktree)
    result = _run_cli(root, "--json", "knowledge", "scaffold", "--project", "acme", "--domain", "nope")
    assert result.returncode == 2
    assert "INVALID_DOMAIN" in result.stdout


# --- T2 (F1): apply change-set engine ---------------------------------------------


def test_apply_dry_run_shows_a_diff_without_writing(bound_worktree, monkeypatch):
    # @ac B-2
    monkeypatch.delenv("WORKTREE_ROOT", raising=False)
    apply_ops("acme", _insert("Gate", "A blocking decision point"), dry_run=False)
    before = glossary_path("acme").read_bytes()

    preview = apply_ops("acme", _insert("Envelope"), dry_run=True)
    assert preview["dry_run"] is True and preview["applied"] is False
    assert "Envelope" in preview["changes"][0]["diff"]
    assert glossary_path("acme").read_bytes() == before


def test_apply_inserts_a_term_and_show_lists_it(bound_worktree, monkeypatch):
    # @ac B-3
    monkeypatch.delenv("WORKTREE_ROOT", raising=False)
    assert apply_ops("acme", _insert(), dry_run=False)["applied"] is True
    assert "Envelope" in glossary_path("acme").read_text(encoding="utf-8")
    assert "envelope" in show_knowledge("acme")["glossary"]


def test_apply_rejects_an_insert_of_an_existing_term_case_insensitively(bound_worktree, monkeypatch):
    # @ac AB-1
    monkeypatch.delenv("WORKTREE_ROOT", raising=False)
    apply_ops("acme", _insert("Gate", "A blocking decision point"), dry_run=False)
    before = glossary_path("acme").read_bytes()
    with pytest.raises(CheError) as exc:
        apply_ops("acme", _insert("gate", "Other"), dry_run=False)
    assert exc.value.code == "KNOWLEDGE_CONFLICT"
    assert glossary_path("acme").read_bytes() == before


def test_apply_rejects_update_and_delete_of_a_missing_term(bound_worktree, monkeypatch):
    # @ac AB-2
    monkeypatch.delenv("WORKTREE_ROOT", raising=False)
    apply_ops("acme", _insert("Gate"), dry_run=False)
    before = glossary_path("acme").read_bytes()
    for op in ({"op": "update", "term": "Foo", "definition": "y"}, {"op": "delete", "term": "Foo"}):
        with pytest.raises(CheError) as exc:
            apply_ops("acme", {"glossary": [op]}, dry_run=False)
        assert exc.value.code == "KNOWLEDGE_CONFLICT"
    assert glossary_path("acme").read_bytes() == before


def test_cli_apply_dry_run_then_confirm_writes(bound_worktree):
    # @ac B-3
    root = _root(bound_worktree)
    ops = '{"glossary":[{"op":"insert","term":"Envelope","definition":"A handoff contract"}]}'

    dry = _run_cli(root, "knowledge", "apply", "--project", "acme", "--ops", ops)
    assert dry.returncode == 0, dry.stderr
    assert "Envelope" in dry.stdout
    assert not glossary_path("acme").is_file()

    applied = _run_cli(root, "knowledge", "apply", "--project", "acme", "--ops", ops, "--no-dry-run", "--confirm")
    assert applied.returncode == 0, applied.stderr
    assert glossary_path("acme").is_file()


def test_cli_apply_requires_confirm_to_write(bound_worktree):
    # @ac B-3
    root = _root(bound_worktree)
    ops = '{"glossary":[{"op":"insert","term":"Envelope","definition":"x"}]}'
    result = _run_cli(root, "knowledge", "apply", "--project", "acme", "--ops", ops, "--no-dry-run")
    assert result.returncode == 2
    assert not glossary_path("acme").is_file()


# --- T3 (F2): conventions topic ops + fail-closed ---------------------------------


def test_apply_update_topic_changes_only_that_topic(bound_worktree, monkeypatch):
    # @ac B-4
    monkeypatch.delenv("WORKTREE_ROOT", raising=False)
    scaffold_conventions("acme", "engineering")
    path = conventions_path("acme", "engineering")
    before = parse_sections(path.read_text(encoding="utf-8"))

    ops = {
        "conventions": [{"domain": "engineering", "op": "update_topic", "topic": "CI Gates", "body": "ruff + pytest."}]
    }
    apply_ops("acme", ops, dry_run=False)

    after = parse_sections(path.read_text(encoding="utf-8"))
    assert after["5. Authoring Rules"] != before["5. Authoring Rules"]
    for key in before:
        if key != "5. Authoring Rules":
            assert after[key] == before[key]
    assert "ruff + pytest." in after["5. Authoring Rules"]


def test_apply_insert_topic_appends_without_renumbering(bound_worktree, monkeypatch):
    # @ac B-4
    monkeypatch.delenv("WORKTREE_ROOT", raising=False)
    scaffold_conventions("acme", "engineering")
    path = conventions_path("acme", "engineering")
    before = parse_topics(parse_sections(path.read_text(encoding="utf-8"))["5. Authoring Rules"])

    ops = {
        "conventions": [
            {"domain": "engineering", "op": "insert_topic", "topic": "Release Notes", "body": "One line per change."}
        ]
    }
    apply_ops("acme", ops, dry_run=False)

    after = parse_topics(parse_sections(path.read_text(encoding="utf-8"))["5. Authoring Rules"])
    assert [title for title, _ in after] == [title for title, _ in before] + ["Release Notes"]
    assert after[-1][1] == "One line per change."


def test_apply_rejects_an_unknown_topic(bound_worktree, monkeypatch):
    # @ac AB-4
    monkeypatch.delenv("WORKTREE_ROOT", raising=False)
    scaffold_conventions("acme", "engineering")
    path = conventions_path("acme", "engineering")
    before = path.read_bytes()
    ops = {"conventions": [{"domain": "engineering", "op": "update_topic", "topic": "Nope", "body": "x"}]}
    with pytest.raises(CheError) as exc:
        apply_ops("acme", ops, dry_run=False)
    assert exc.value.code == "KNOWLEDGE_CONFLICT"
    assert path.read_bytes() == before


def test_apply_rejects_a_conventions_op_without_a_scaffolded_domain(bound_worktree, monkeypatch):
    # @ac AB-4
    monkeypatch.delenv("WORKTREE_ROOT", raising=False)
    ops = {"conventions": [{"domain": "devops", "op": "insert_topic", "topic": "New", "body": "x"}]}
    with pytest.raises(CheError) as exc:
        apply_ops("acme", ops, dry_run=False)
    assert exc.value.code == "KNOWLEDGE_CONFLICT"


def test_cli_apply_rejects_malformed_ops_json(bound_worktree):
    # @ac AB-4
    root = _root(bound_worktree)
    result = _run_cli(root, "--json", "knowledge", "apply", "--project", "acme", "--ops", "{not json")
    assert result.returncode == 2
    assert "KNOWLEDGE_INPUT_INVALID" in result.stdout


def test_cli_apply_reads_ops_from_a_file(bound_worktree, tmp_path):
    root = _root(bound_worktree)
    ops_file = tmp_path / "ops.json"
    ops_file.write_text('{"glossary":[{"op":"insert","term":"Envelope","definition":"x"}]}', encoding="utf-8")
    result = _run_cli(root, "knowledge", "apply", "--project", "acme", "--ops", f"@{ops_file}")
    assert result.returncode == 0, result.stderr


def test_cli_apply_reports_a_missing_ops_file_actionably(bound_worktree):
    # @ac AB-4
    root = _root(bound_worktree)
    result = _run_cli(root, "--json", "knowledge", "apply", "--project", "acme", "--ops", "@/no/such/ops.json")
    assert result.returncode == 2
    assert "KNOWLEDGE_INPUT_INVALID" in result.stdout


# --- T4 (F3): determinism + capabilities ------------------------------------------


def test_glossary_renders_in_canonical_order_without_temp_residue(bound_worktree, monkeypatch):
    # @ac B-6
    monkeypatch.delenv("WORKTREE_ROOT", raising=False)
    ops = {
        "glossary": [
            {"op": "insert", "term": "Zeta", "definition": "z"},
            {"op": "insert", "term": "Alpha", "definition": "a"},
        ]
    }
    apply_ops("acme", ops, dry_run=False)
    text = glossary_path("acme").read_text(encoding="utf-8")
    assert text.index("Alpha") < text.index("Zeta")
    assert list(glossary_path("acme").parent.glob("*.tmp.*")) == []


def test_glossary_render_is_order_independent():
    # @ac B-6
    rows = {
        "alpha": {
            "Term": "Alpha",
            "Definition": "a",
            "Aliases": "",
            "Domain": "",
            "Source": "",
            "Updated": "2026-01-01",
        },
        "zeta": {"Term": "Zeta", "Definition": "z", "Aliases": "", "Domain": "", "Source": "", "Updated": "2026-01-01"},
    }
    forward = render_glossary("acme", dict(rows))
    backward = render_glossary("acme", dict(reversed(list(rows.items()))))
    assert forward == backward


def test_glossary_round_trips_special_characters(bound_worktree, monkeypatch):
    # @ac B-6
    monkeypatch.delenv("WORKTREE_ROOT", raising=False)
    ops = {"glossary": [{"op": "insert", "term": "A|B", "definition": "line one\nline two | pipe"}]}
    apply_ops("acme", ops, dry_run=False)
    terms = parse_glossary(glossary_path("acme").read_text(encoding="utf-8"))
    assert "a|b" in terms
    assert terms["a|b"]["Definition"] == "line one line two | pipe"


def test_capabilities_lists_the_knowledge_commands(bound_worktree):
    # @ac B-7
    root = _root(bound_worktree)
    result = _run_cli(root, "--json", "capabilities")
    assert result.returncode == 0, result.stderr
    for name in ('"knowledge scaffold"', '"knowledge show"', '"knowledge apply"'):
        assert name in result.stdout
