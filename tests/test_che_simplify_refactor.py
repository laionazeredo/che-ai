"""Contract test for che-simplify and che-refactor — the two reduction skills.

che-simplify is a *planning* rule (goals fixed, essential vs accidental); che-refactor is an
*execution* rule (behaviour-preserving). Both are process rules: deleting their invariants breaks
nothing at runtime, so these assertions are the only thing that turns silent drift into a CI failure.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

CHE_ROOT = Path(__file__).resolve().parent.parent

SIMPLIFY = "skills/che-simplify/SKILL.md"
REFACTOR = "skills/che-refactor/SKILL.md"

SIMPLIFY_ANCHORS = [
    "The GOALS are fixed",
    "Essential",
    "Accidental",
    "Decision trail",
    "Never cut essential complexity",
    "che compute_paths",
    "CHE_WORKSPACE_SHARED",
    "stdin",
]

REFACTOR_ANCHORS = [
    "behaviour-preserving",
    "characterization tests",
    "must be green",
    "NEVER inside `che-ship`",
    "Measurable target",
    "che compute_paths",
    "CHE_WORKSPACE_SHARED",
    "stdin",
]

COMMANDS = {
    "commands/che-simplify.md": "che-simplify",
    "commands/che-refactor.md": "che-refactor",
}


def _read(relative: str) -> str:
    return (CHE_ROOT / relative).read_text(encoding="utf-8")


@pytest.mark.parametrize("anchor", SIMPLIFY_ANCHORS)
def test_simplify_contract_keeps_its_anchors(anchor: str) -> None:
    assert anchor in _read(SIMPLIFY), f"che-simplify lost the anchor: {anchor!r}"


@pytest.mark.parametrize("anchor", REFACTOR_ANCHORS)
def test_refactor_contract_keeps_its_anchors(anchor: str) -> None:
    assert anchor in _read(REFACTOR), f"che-refactor lost the anchor: {anchor!r}"


@pytest.mark.parametrize("relative,skill", COMMANDS.items())
def test_command_invokes_its_skill(relative: str, skill: str) -> None:
    assert skill in _read(relative), f"{relative} no longer invokes {skill}"


def test_che_commands_lists_both() -> None:
    commands = _read("CHE_COMMANDS.md")

    assert "/che-simplify" in commands
    assert "/che-refactor" in commands


def _category_a_counts(text: str) -> tuple[int, int]:
    """Return (advertised, actual) row counts for the Category A table."""
    lines = text.splitlines()
    heading = next(line for line in lines if line.startswith("### Category A"))
    advertised = int(re.search(r"\d+", heading).group())
    actual = 0
    for line in lines[lines.index(heading) + 1 :]:
        if line.startswith("###"):
            break
        if line.startswith("| `/che-"):
            actual += 1
    return advertised, actual


def test_che_commands_advertised_count_matches_the_table() -> None:
    advertised, actual = _category_a_counts(_read("CHE_COMMANDS.md"))

    assert advertised == actual, f"CHE_COMMANDS.md advertises {advertised} heavy commands but lists {actual} rows"


@pytest.mark.parametrize("skill", ["che-simplify", "che-refactor"])
def test_paperclip_package_mirrors_the_skills(skill: str) -> None:
    assert skill in _read(f"paperclip/package/skills/{skill}/SKILL.md")
