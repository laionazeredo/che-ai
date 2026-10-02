"""Contract test for the Simplicity Bias — the touchstone that must stay wired.

The bias is a *rule*, so deleting it breaks nothing at runtime: planning silently drifts back to
maximalist solutions and no test goes red. These assertions turn that silence into a CI failure.
They are deliberately narrow — they pin the canonical body and its references, not the prose.
"""

from __future__ import annotations

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

#: The ordered criteria the bias must state — and must state in this priority order.
ORDERED_CRITERIA = ["Smallest first increment", "Most reversible", "Most observable"]


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
def test_every_decision_point_references_the_bias(relative: str) -> None:
    assert "simplicity bias" in _read(relative).lower(), f"{relative} no longer references the Simplicity Bias"
