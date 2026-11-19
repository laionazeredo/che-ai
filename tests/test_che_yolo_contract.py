"""Contract test for /che-yolo — the autonomous end-to-end path.

The command is prose, so nothing fails at runtime when a safety anchor disappears: the next edit
quietly turns "ship behind five gates, then ask a human" into "merge whatever is green". These
assertions pin the anchors that make the autonomy bounded.
"""

from __future__ import annotations

from pathlib import Path

import pytest

CHE_ROOT = Path(__file__).resolve().parent.parent

COMMAND = "commands/che-yolo.md"
SKILL = "skills/che-yolo/SKILL.md"
ROUTER = "CHE_COMMANDS.md"

ANCHORS = {
    COMMAND: [
        "che-yolo",
        "Approved SPEC",
        "gh auth status",
    ],
    SKILL: [
        "Approved SPEC",
        "REVIEW_MODE=FINAL",
        "che manual-plan validate",
        "0.9.1",
        "che-ship",
        "che-manual-test-executor",
        "gh pr comment",
        "gh pr ready",
        "one vertical slice = one commit",
        "Never merges",
        "Windows and shell portability",
    ],
    ROUTER: [
        "`/che-yolo`",
        "`che-yolo`",
        "never merges",
    ],
}


def _read(relative: str) -> str:
    return (CHE_ROOT / relative).read_text(encoding="utf-8")


@pytest.mark.parametrize("relative,anchor", [(f, a) for f, anchors in ANCHORS.items() for a in anchors])
def test_yolo_keeps_its_contract_anchors(relative: str, anchor: str) -> None:
    assert anchor in _read(relative), f"{relative} lost the contract anchor: {anchor!r}"


@pytest.mark.parametrize("relative", [COMMAND, SKILL])
def test_yolo_never_merges_or_force_pushes(relative: str) -> None:
    text = _read(relative).lower()
    assert "gh pr merge" not in text, f"{relative} must never merge the PR"
    assert "--force" not in text, f"{relative} must never force-push"


def test_yolo_skill_frontmatter_names_the_skill() -> None:
    text = _read(SKILL)
    assert text.startswith("---\n")
    assert 'name: "che-yolo"' in text
