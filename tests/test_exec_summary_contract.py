"""Contract test for the human-first executive summary (§0 SPEC / Plan at a glance task graph).

The summary is a *presentation* contract: if it silently disappears, drifts from the machine sections or
grows into a second spec, nothing fails at runtime and the human goes back to reading a 120-line draft to
approve. These assertions pin its position, its cap and its derived-not-authoritative rule.
"""

from __future__ import annotations

from pathlib import Path

import pytest

CHE_ROOT = Path(__file__).resolve().parent.parent

SPEC = "skills/che-spec/SKILL.md"
ACT = "skills/che-act/SKILL.md"

#: Anchors the SPEC summary must keep.
SPEC_ANCHORS = [
    "## §0 EXECUTIVE SUMMARY",
    "DERIVED never authoritative",
    "Cap: 15 lines total",
    "Decisions needed from you",
    "Out of scope",
    "Non-goals (deferred by design)",
    "V25 Executive summary",
    "D = show full draft",
]

#: Anchors the task-graph summary must keep.
ACT_ANCHORS = [
    "## Executive Summary (human-first",
    "## Plan at a glance",
    "DERIVED never authoritative",
    "G-ES",
    "D = show full task list",
]


def _read(relative: str) -> str:
    return (CHE_ROOT / relative).read_text(encoding="utf-8")


@pytest.mark.parametrize("anchor", SPEC_ANCHORS)
def test_spec_summary_keeps_its_anchors(anchor: str) -> None:
    assert anchor in _read(SPEC), f"che-spec lost the executive-summary anchor: {anchor!r}"


@pytest.mark.parametrize("anchor", ACT_ANCHORS)
def test_act_summary_keeps_its_anchors(anchor: str) -> None:
    assert anchor in _read(ACT), f"che-act lost the executive-summary anchor: {anchor!r}"


def test_spec_summary_sits_before_the_machine_sections() -> None:
    spec = _read(SPEC)

    assert spec.index("## §0 EXECUTIVE SUMMARY") < spec.index("### §1 WHY")


def test_act_summary_sits_before_the_task_table() -> None:
    act = _read(ACT)

    assert act.index("## Executive Summary (human-first") < act.index("## Task Table")
    assert act.index("## Plan at a glance") < act.index("## Task Table")


def test_approval_shows_the_summary_not_the_full_draft() -> None:
    spec = _read(SPEC)

    assert "Show ONLY the §0 EXECUTIVE SUMMARY" in spec


def test_paperclip_package_mirrors_the_summary() -> None:
    assert "## Plan at a glance" in _read("paperclip/package/skills/che-act/SKILL.md")
    assert "DERIVED never authoritative" in _read("paperclip/package/skills/che-spec/SKILL.md")
