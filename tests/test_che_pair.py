"""Contract test for che-pair — the increment skeptic that must stay bounded.

che-pair is a *process* rule: if the loop bounds or the citation requirement are deleted, nothing
fails at runtime and the dev<->skeptic loop can spin forever. These assertions pin the contract
anchors, the wiring into che-act and che-developer, and the Paperclip mirror.
"""

from __future__ import annotations

from pathlib import Path

import pytest

CHE_ROOT = Path(__file__).resolve().parent.parent

PAIR = "skills/che-pair/SKILL.md"

#: Anchors the pair contract must keep — trigger, lenses, citation, bounds, enforcement.
CONTRACT_ANCHORS = [
    "END of each vertical slice",
    "LENSES (FROZEN",
    "Citation required",
    "Max 2 rounds per slice",
    "No-progress stop",
    "CRITICAL",
    "deferred by design",
    "ESCALATION MENU",
]

#: Files that must reference the pair at their decision point.
WIRING = {
    "skills/che-act/SKILL.md": "che-pair",
    "skills/che-developer/SKILL.md": "che-pair",
}


def _read(relative: str) -> str:
    return (CHE_ROOT / relative).read_text(encoding="utf-8")


@pytest.mark.parametrize("anchor", CONTRACT_ANCHORS)
def test_pair_contract_keeps_its_anchors(anchor: str) -> None:
    assert anchor in _read(PAIR), f"che-pair lost the contract anchor: {anchor!r}"


@pytest.mark.parametrize("relative,fragment", WIRING.items())
def test_act_loop_wires_the_pair(relative: str, fragment: str) -> None:
    assert fragment in _read(relative), f"{relative} no longer references {fragment}"


def test_envelope_carries_slices_and_deferred_list() -> None:
    envelope = _read("skills/che-act/references/TASK_ENVELOPE_TEMPLATE.md")

    assert "Vertical Slices" in envelope
    assert "deferred by design" in envelope.lower()


def test_paperclip_package_mirrors_the_pair() -> None:
    assert "Max 2 rounds per slice" in _read("paperclip/package/skills/che-pair/SKILL.md")
