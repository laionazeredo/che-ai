"""Contract test for che-interrogate — the pre-planning readiness gate.

che-interrogate is a *process* rule: if the evidence hierarchy, the question bounds or the blocking
policy are deleted, nothing fails at runtime and the gate degrades into an unbounded interrogation
(blocking on market taste) or into a no-op. These assertions pin the contract anchors and the wiring
into che-spec (raw input, earliest possible) and che-act (before scope capture), plus the mirror.
"""

from __future__ import annotations

from pathlib import Path

import pytest

CHE_ROOT = Path(__file__).resolve().parent.parent

INTERROGATE = "skills/che-interrogate/SKILL.md"

#: Anchors the readiness contract must keep — hierarchy, question bounds, severity, output.
CONTRACT_ANCHORS = [
    "EVIDENCE HIERARCHY (FROZEN",
    "Code already implemented in the bound worktree",
    "Past decisions",
    "Established conventions",
    "Market best practice",
    "level 4 is the weakest evidence",
    "LENSES (FROZEN per mode",
    "QUESTION CONTRACT",
    "Max 5 questions per round",
    "Max 2 rounds per mode",
    "No-progress stop",
    "SEVERITY GATE",
    "**BLOCKER**",
    "**MAJOR**",
    "ESCALATION MENU",
    "READINESS_VERDICT=READY|READY_WITH_ASSUMPTIONS|BLOCKED",
    "che output_path report readiness",
    "che write_file_atomic",
    "READINESS_GATE",
    "not found",
]

#: Files that must reference the gate at their decision point.
WIRING = {
    "skills/che-spec/SKILL.md": "che-interrogate",
    "skills/che-act/SKILL.md": "che-interrogate",
}

#: The gate must run on the RAW input before drafting, and before scope capture.
POSITION_ANCHORS = {
    "skills/che-spec/SKILL.md": "INTAKE READINESS GATE",
    "skills/che-act/SKILL.md": "PRE-PLAN READINESS GATE",
}

#: Frontmatter persistence consumed by che-act to avoid re-asking.
SPEC_FRONTMATTER_KEYS = ["readiness:", "readiness_report:", "open_assumptions:"]


def _read(relative: str) -> str:
    return (CHE_ROOT / relative).read_text(encoding="utf-8")


@pytest.mark.parametrize("anchor", CONTRACT_ANCHORS)
def test_interrogate_contract_keeps_its_anchors(anchor: str) -> None:
    assert anchor in _read(INTERROGATE), f"che-interrogate lost the contract anchor: {anchor!r}"


@pytest.mark.parametrize("relative,fragment", WIRING.items())
def test_flow_wires_the_gate(relative: str, fragment: str) -> None:
    assert fragment in _read(relative), f"{relative} no longer references {fragment}"


@pytest.mark.parametrize("relative,fragment", POSITION_ANCHORS.items())
def test_gate_runs_early_in_the_planning_cycle(relative: str, fragment: str) -> None:
    assert fragment in _read(relative), f"{relative} lost its readiness gate section: {fragment}"


@pytest.mark.parametrize("key", SPEC_FRONTMATTER_KEYS)
def test_spec_persists_the_readiness_result(key: str) -> None:
    assert key in _read("skills/che-spec/SKILL.md"), f"che-spec no longer persists {key!r}"


def test_intake_gate_precedes_source_selection() -> None:
    spec = _read("skills/che-spec/SKILL.md")

    assert spec.index("INTAKE READINESS GATE") < spec.index("## §2 SOURCE SELECTION")


def test_act_gate_precedes_scope_capture() -> None:
    act = _read("skills/che-act/SKILL.md")

    assert act.index("PRE-PLAN READINESS GATE") < act.index("### 1.1 Input validation")


def test_paperclip_package_mirrors_the_gate() -> None:
    assert "Max 2 rounds per mode" in _read("paperclip/package/skills/che-interrogate/SKILL.md")
