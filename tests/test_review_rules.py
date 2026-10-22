"""Contract tests for the review-rule resolver behind `che review rules`.

The resolver exists so a review never has to decide, mid-sentence, which of two contradictory
project rules to believe. Three properties make that true, and each has its own block below:
discovery is layered, applicability is path-scoped, and precedence is deterministic — including
when it cannot decide, in which case the conflict is reported and capped instead of resolved.
"""

from __future__ import annotations

import json
from pathlib import Path

from che_core.cli import main
from che_core.review_rules import SEVERITY_RANK, resolve_review_rules


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _cards(result: dict, suffix: str) -> list:
    return [card for card in result["rules"] if card["source"].endswith(suffix)]


# ---------------------------------------------------------------------------------------------
# Discovery — every source is classified into the layer it speaks from
# ---------------------------------------------------------------------------------------------


def test_rules_are_discovered_from_the_repository_and_from_project_memory(bound_worktree) -> None:
    repo, paths = bound_worktree
    _write(repo / "AGENTS.md", "# Repo\n\n## Architecture\n\nNever put business logic in routers.\n")
    _write(repo / ".claude" / "rules" / "testing.md", "# Testing\n\n## Coverage\n\nTests must cover the happy path.\n")
    _write(
        Path(paths["CHE_PROJECT_DIR"]) / "engineering" / "conventions.md",
        "# Conventions\n\n## Testing\n\nTests must run on every commit.\n",
    )

    result = resolve_review_rules(str(repo), project="acme", changed=["apps/api/route.ts"])

    layers = {card["source"].split("/")[-1]: card["layer"] for card in result["rules"]}
    assert layers["AGENTS.md"] == "repo-explicit"
    assert layers["testing.md"] == "repo-explicit"
    assert layers["conventions.md"] == "project-memory"


def test_a_machine_enforced_config_is_listed_without_becoming_a_prose_rule(bound_worktree) -> None:
    """Lint config already gates style; naming it is useful, turning it into a rule is not."""
    repo, _ = bound_worktree
    _write(repo / "tsconfig.json", "{}\n")

    result = resolve_review_rules(str(repo), changed=["src/index.ts"])

    machine = [source for source in result["sources"] if source["layer"] == "machine"]
    assert [source["path"].split("/")[-1] for source in machine] == ["tsconfig.json"]
    assert machine[0]["rules"] == 0


def test_a_package_document_only_scopes_the_package_it_lives_in(bound_worktree) -> None:
    repo, _ = bound_worktree
    _write(repo / "packages" / "api" / "AGENTS.md", "# API\n\n## Layering\n\nRouters must not query the database.\n")

    inside = resolve_review_rules(str(repo), changed=["packages/api/routers/booking.ts"])
    outside = resolve_review_rules(str(repo), changed=["web/page.tsx"])

    assert _cards(inside, "packages/api/AGENTS.md")
    assert not _cards(outside, "packages/api/AGENTS.md")


# ---------------------------------------------------------------------------------------------
# Applicability — a rule that speaks about other files is not applied to this diff
# ---------------------------------------------------------------------------------------------


def test_a_rule_scoped_to_untouched_paths_is_excluded_and_named(bound_worktree) -> None:
    repo, _ = bound_worktree
    _write(
        repo / ".claude" / "rules" / "api.md",
        "---\npaths: [apps/api/**]\n---\n\n## Layering\n\nRouters must not query the database directly.\n",
    )

    result = resolve_review_rules(str(repo), changed=["web/page.tsx"])

    assert not _cards(result, "api.md")
    assert any(entry["path"].endswith("api.md") and "path-scoped" in entry["reason"] for entry in result["ignored"])


def test_the_changed_list_defaults_to_the_worktree_status(bound_worktree) -> None:
    repo, _ = bound_worktree
    _write(repo / "apps" / "api" / "route.ts", "export const x = 1;\n")
    _write(
        repo / ".claude" / "rules" / "api.md",
        "---\npaths: [apps/api/**]\n---\n\n## Layering\n\nRouters must not query the database.\n",
    )

    result = resolve_review_rules(str(repo))

    assert "apps/api/route.ts" in result["changed_files"]
    assert result["scope_mode"] == "diff"
    assert _cards(result, "api.md")


# ---------------------------------------------------------------------------------------------
# Precedence — a lower layer never silently outranks a higher one
# ---------------------------------------------------------------------------------------------


def test_the_repository_rule_supersedes_contradictory_project_memory(bound_worktree) -> None:
    repo, paths = bound_worktree
    _write(repo / "AGENTS.md", "# Repo\n\n## Architecture\n\nRouters must not contain business logic.\n")
    _write(
        Path(paths["CHE_PROJECT_DIR"]) / "engineering" / "conventions.md",
        "# Conventions\n\n## Architecture\n\nRouters must contain business logic.\n",
    )

    result = resolve_review_rules(str(repo), project="acme", changed=["apps/api/route.ts"])

    assert [conflict["kind"] for conflict in result["conflicts"]] == ["precedence"]
    assert result["conflicts"][0]["winner_source"].endswith("AGENTS.md:5")
    stale = _cards(result, "conventions.md")
    assert stale and stale[0]["superseded_by"]
    assert [entry["topic"] for entry in result["drift"]] == ["layering"]


def test_two_rules_of_the_same_layer_are_reported_and_capped_not_silently_picked(bound_worktree) -> None:
    repo, _ = bound_worktree
    _write(
        repo / ".claude" / "rules" / "a.md",
        "# A\n\n## Coverage\n\nTests must never be skipped without a ticket.\n",
    )
    _write(
        repo / ".claude" / "rules" / "b.md",
        "# B\n\n## Coverage\n\nTests must enforce a coverage threshold.\n",
    )

    result = resolve_review_rules(str(repo), changed=["src/index.ts"])

    assert [conflict["kind"] for conflict in result["conflicts"]] == ["unresolved"]
    assert all(card["conflicted"] for card in _cards(result, "a.md") + _cards(result, "b.md"))
    assert all(
        SEVERITY_RANK[card["effective_severity"]] <= SEVERITY_RANK["MEDIUM"]
        for card in _cards(result, "a.md") + _cards(result, "b.md")
    )


def test_the_hard_floor_is_always_present_and_never_overridable(bound_worktree) -> None:
    repo, _ = bound_worktree

    result = resolve_review_rules(str(repo), changed=["src/index.ts"])

    assert result["hard_floor"], "the Che invariants must not depend on project files existing"
    assert all(entry["overridable"] is False for entry in result["hard_floor"])
    assert {topic for entry in result["hard_floor"] for topic in entry["topics"]} >= {"security", "storage-boundary"}


# ---------------------------------------------------------------------------------------------
# Review parameters — project-declared, session-overridable, bounded
# ---------------------------------------------------------------------------------------------


def test_project_review_parameters_come_from_the_profile_frontmatter(bound_worktree) -> None:
    repo, paths = bound_worktree
    _write(
        Path(paths["CHE_PROJECT_DIR"]) / "project_profile.md",
        "---\n"
        "review:\n"
        "  min_severity: HIGH\n"
        "  blocking: [CRITICAL]\n"
        '  ignore_paths: ["**/generated/**"]\n'
        "  max_rules: 5\n"
        "---\n\n# Profile\n",
    )

    result = resolve_review_rules(str(repo), project="acme", changed=["src/index.ts"])

    assert result["params"]["min_severity"] == "HIGH"
    assert result["params"]["blocking"] == ["CRITICAL"]
    assert result["params"]["ignore_paths"] == ["**/generated/**"]
    assert result["params"]["max_rules"] == 5


def test_session_overrides_win_over_the_project_profile(bound_worktree) -> None:
    repo, paths = bound_worktree
    _write(
        Path(paths["CHE_PROJECT_DIR"]) / "project_profile.md",
        "---\nreview:\n  min_severity: HIGH\n---\n\n# Profile\n",
    )

    result = resolve_review_rules(
        str(repo),
        project="acme",
        changed=["src/index.ts"],
        overrides={"min_severity": "CRITICAL"},
    )

    assert result["params"]["min_severity"] == "CRITICAL"


def test_a_severity_floor_filters_rules_but_never_the_hard_floor(bound_worktree) -> None:
    repo, _ = bound_worktree
    _write(repo / "AGENTS.md", "# Repo\n\n## Naming\n\nFiles should be named after their export.\n")

    result = resolve_review_rules(
        str(repo),
        changed=["src/index.ts"],
        overrides={"min_severity": "CRITICAL"},
    )

    assert not _cards(result, "AGENTS.md")
    assert any("below min_severity" in entry["reason"] for entry in result["ignored"])
    assert result["hard_floor"]


def test_the_rule_budget_truncates_by_authority_and_says_so(bound_worktree) -> None:
    repo, _ = bound_worktree
    _write(repo / "AGENTS.md", "# Repo\n\n## Naming\n\nFiles must be named after their export.\n")
    _write(repo / ".claude" / "rules" / "one.md", "# One\n\n## Testing\n\nTests must be deterministic.\n")
    _write(repo / ".claude" / "rules" / "two.md", "# Two\n\n## Logging\n\nLogs must not contain PII.\n")

    result = resolve_review_rules(str(repo), changed=["src/index.ts"], overrides={"max_rules": 1})

    assert len(result["rules"]) == 1
    assert result["budget"]["truncated"] is True
    assert result["budget"]["rules_available"] > 1


# ---------------------------------------------------------------------------------------------
# The CLI surface — one command, the same document
# ---------------------------------------------------------------------------------------------


def test_the_command_prints_the_resolution_as_json(bound_worktree, capsys) -> None:
    repo, _ = bound_worktree
    _write(repo / "AGENTS.md", "# Repo\n\n## Naming\n\nFiles must be named after their export.\n")

    main(["--json", "review", "rules", "--worktree", str(repo), "--changed", "src/index.ts"])

    payload = json.loads(capsys.readouterr().out)
    assert set(payload) >= {"params", "rules", "hard_floor", "conflicts", "sources", "budget"}
    assert [card["layer"] for card in payload["rules"]] == ["repo-explicit"]
