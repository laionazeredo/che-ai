"""Contract test for the Simplicity Bias — the touchstone that must stay wired.

The bias is a *rule*, so deleting it breaks nothing at runtime: planning silently drifts back to
maximalist solutions and no test goes red. These assertions turn that silence into a CI failure.
They pin the canonical body, a real reference at every decision point, and the Paperclip mirror —
not the prose around them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

CHE_ROOT = Path(__file__).resolve().parent.parent

#: The single source of truth for the bias body (engineering-contracts §1).
CANONICAL = "skills/engineering-contracts/SKILL.md"

#: Every decision point that must reference the canonical body: planning, execution, review.
REFERENCING_FILES = [
    "AGENTS.md",
    "skills/che-spec/SKILL.md",
    "skills/che-architect/SKILL.md",
    "skills/che-plan/SKILL.md",
    "skills/che-act/SKILL.md",
    "skills/che-developer/SKILL.md",
    "skills/che-scope-checker/SKILL.md",
    "skills/che-code-review/SKILL.md",
    "skills/che-social-ui-designer/SKILL.md",
]

#: The ordered criteria the canonical body must state — and must state in this priority order.
ORDERED_CRITERIA = ["Smallest first increment", "Most reversible", "Most observable"]

#: A reference to the canonical rule, tolerant of markdown/backticks around the section sign.
CANONICAL_REF = re.compile(r"engineering-contracts\W{0,3}§1", re.IGNORECASE)

#: Skills mirrored into the Paperclip package that must carry the same reference.
PACKAGED_SKILLS = [
    "che-spec",
    "che-architect",
    "che-plan",
    "che-act",
    "che-developer",
    "che-scope-checker",
    "che-code-review",
    "che-social-ui-designer",
]


def _read(relative: str) -> str:
    return (CHE_ROOT / relative).read_text(encoding="utf-8")


def test_canonical_body_states_the_ordered_bias() -> None:
    body = _read(CANONICAL)

    assert "SIMPLICITY BIAS" in body
    positions = [body.find(criterion) for criterion in ORDERED_CRITERIA]
    assert all(position != -1 for position in positions), positions
    assert positions == sorted(positions), "the criteria must appear in priority order"


def test_canonical_body_defers_completeness_and_requires_justification() -> None:
    body = _read(CANONICAL)

    assert "JUSTIFY-OR-DEFER" in body
    assert "defer" in body.lower()


def test_bias_never_overrides_security() -> None:
    assert "never trade safety for simplicity" in _read(CANONICAL).lower()


@pytest.mark.parametrize("relative", REFERENCING_FILES)
def test_every_decision_point_references_the_canonical_rule(relative: str) -> None:
    mentions = [line for line in _read(relative).splitlines() if "simplicity bias" in line.lower()]

    assert mentions, f"{relative} no longer mentions the Simplicity Bias"
    assert any(CANONICAL_REF.search(line) for line in mentions), (
        f"{relative} mentions the Simplicity Bias without referencing engineering-contracts §1"
    )


@pytest.mark.parametrize("relative", REFERENCING_FILES)
def test_referencing_files_do_not_duplicate_the_canonical_body(relative: str) -> None:
    lowered = _read(relative).lower()
    restated = [criterion for criterion in ORDERED_CRITERIA if criterion.lower() in lowered]

    assert not restated, f"{relative} restates the canonical body instead of referencing it: {restated}"


def test_paperclip_package_mirrors_the_canonical_bias() -> None:
    assert "SIMPLICITY BIAS" in _read("paperclip/package/skills/engineering-contracts/SKILL.md")


@pytest.mark.parametrize("skill", PACKAGED_SKILLS)
def test_paperclip_package_skills_reference_the_bias(skill: str) -> None:
    packaged = _read(f"paperclip/package/skills/{skill}/SKILL.md")

    assert "simplicity bias" in packaged.lower(), f"packaged {skill} is out of sync with skills/{skill}"
    assert CANONICAL_REF.search(packaged), f"packaged {skill} lost the engineering-contracts §1 reference"
