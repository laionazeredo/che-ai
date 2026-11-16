"""Contract test for che-manual-verification — the plain-language verification guide.

The skill is a *document* contract: nothing breaks at runtime if its three answers, its lane
decision or its boundary against the executor disappear, so these assertions are what turns
silent drift into a CI failure.
"""

from __future__ import annotations

from pathlib import Path

import pytest

CHE_ROOT = Path(__file__).resolve().parent.parent

SKILL = "skills/che-manual-verification/SKILL.md"
COMMAND = "commands/che-manual-verification.md"

SKILL_ANCHORS = [
    "What does this increment do?",
    "How do I prove it by hand?",
    "What if I cannot test it here?",
    "§4 Lane A",
    "§5 Lane B",
    "§6 Lane C",
    "PASS / FAIL / BLOCKED",
    "Never execute",
    "che output_path",
    "CHE_WORKSPACE_SHARED",
]


def _read(relative: str) -> str:
    return (CHE_ROOT / relative).read_text(encoding="utf-8")


@pytest.mark.parametrize("anchor", SKILL_ANCHORS)
def test_skill_keeps_its_contract_anchors(anchor: str) -> None:
    assert anchor in _read(SKILL), f"{SKILL} lost the anchor: {anchor!r}"


def test_command_invokes_the_skill() -> None:
    assert "che-manual-verification" in _read(COMMAND)


def test_che_commands_lists_the_command() -> None:
    commands = _read("CHE_COMMANDS.md")

    assert "| `/che-manual-verification" in commands
    assert "## `/che-manual-verification" in commands


def test_skill_stays_out_of_the_executor_and_the_verdict() -> None:
    skill = _read(SKILL)

    assert "never executes it" in skill
    assert "No verdict" in skill
