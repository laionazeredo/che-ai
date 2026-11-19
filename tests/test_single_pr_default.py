"""Contract test for the single-PR default.

Che delivers ONE PR unless the user explicitly asks for a stack. This is a process rule: when the
anchors disappear, the size heuristic comes back and the agent silently splits a delivery into a
gh-stack the user never requested. These assertions pin the opt-in boundary and keep the capability
itself alive for when the user does ask.
"""

from __future__ import annotations

from pathlib import Path

import pytest

CHE_ROOT = Path(__file__).resolve().parent.parent

ACT = "skills/che-act/SKILL.md"
SHIP = "skills/che-ship/SKILL.md"
RULES = "CHE_RULES.md"
CONTRACTS = "skills/engineering-contracts/SKILL.md"
REFERENCE = "REFERENCE_USER_RULES_MINIFIED.md"

ANCHORS = {
    ACT: [
        "EXPLICIT OPT-IN ONLY",
        "Default delivery is ONE PR",
        "GH_STACK_REQUESTED",
    ],
    SHIP: [
        "EXPLICIT OPT-IN ONLY",
        "GH_STACK_REQUESTED",
    ],
    RULES: [
        "EXPLICIT OPT-IN ONLY",
        "never proposed automatically",
    ],
    CONTRACTS: [
        "opt-in only",
        "The user explicitly requested a stack",
    ],
    REFERENCE: [
        "ONE PR by default",
    ],
}


def _read(relative: str) -> str:
    return (CHE_ROOT / relative).read_text(encoding="utf-8")


@pytest.mark.parametrize("relative,anchor", [(f, a) for f, anchors in ANCHORS.items() for a in anchors])
def test_single_pr_default_keeps_its_anchors(relative: str, anchor: str) -> None:
    assert anchor in _read(relative), f"{relative} lost the single-PR contract anchor: {anchor!r}"


def test_che_act_no_longer_uses_a_size_threshold() -> None:
    text = _read(ACT)
    assert "Total tasks >= 3" not in text
    assert "threshold-triggered" not in text
    assert "blast radius > 15 files" not in text


def test_gh_stack_capability_still_exists_for_explicit_requests() -> None:
    assert (CHE_ROOT / "skills/gh-stack/SKILL.md").is_file()
