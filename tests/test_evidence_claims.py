"""Contract test for Evidence-Based Claims (§0) — the rule that keeps assertions auditable.

The rule is prompt-layer only: deleting it breaks nothing at runtime, the agent simply drifts back
to confident, uncited assertions and the user discovers it after a correction. These assertions
turn that silence into a CI failure. They pin the canonical body, its precedence position, the
reference at every flow that makes claims, and the absence of a restated body.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

CHE_ROOT = Path(__file__).resolve().parent.parent

#: The single source of truth for the evidence-based-claims rule text.
CANONICAL = "skills/engineering-contracts/SKILL.md"

#: Every flow that asserts something to the user or into an artifact.
#: `user_rules/` is gitignored, so it is intentionally absent here.
REFERENCING_FILES = [
    "CHE_RULES.md",
    "skills/che-spec/SKILL.md",
    "skills/che-code-review/SKILL.md",
    "skills/che-debugger-bugfix/SKILL.md",
    "skills/che-interrogate/SKILL.md",
    "skills/che-architect/SKILL.md",
]

#: The three labels — the only allowed forms of an assertion.
LABELS = ["[verified:", "[inference:", "[unknown:"]

#: Evidence classes, strongest first. The order is part of the contract.
EVIDENCE_CLASSES = [
    "E1 Artifact",
    "E2 Authoritative doc",
    "E3 Recorded decision",
    "E4 Observed convention",
    "E5 Inference",
]

#: A reference to the canonical rule, tolerant of markdown/backticks around the section sign.
CANONICAL_REF = re.compile(r"engineering-contracts\W{0,3}§0", re.IGNORECASE)


def _read(relative: str) -> str:
    return (CHE_ROOT / relative).read_text(encoding="utf-8")


def test_canonical_body_defines_the_three_labels() -> None:
    body = _read(CANONICAL)

    assert "EVIDENCE-BASED CLAIMS" in body
    missing = [label for label in LABELS if label not in body]
    assert not missing, f"labels missing from the canonical body: {missing}"


def test_canonical_body_orders_evidence_classes_strongest_first() -> None:
    body = _read(CANONICAL)

    positions = [body.find(evidence_class) for evidence_class in EVIDENCE_CLASSES]
    assert all(position != -1 for position in positions), positions
    assert positions == sorted(positions), "evidence classes must appear strongest first"


def test_canonical_body_requires_a_correction_protocol() -> None:
    body = _read(CANONICAL)

    assert "CLAIM_CORRECTION" in body
    assert "correction protocol" in body.lower()


def test_evidence_rule_outranks_kiss() -> None:
    body = _read(CANONICAL)

    rule_zero = body.find("### 0. ")
    kiss = body.find("### 1. ")
    assert rule_zero != -1 and kiss != -1, "precedence headings are missing"
    assert rule_zero < kiss, "the evidence rule must sit above KISS in the precedence order"


@pytest.mark.parametrize("relative", REFERENCING_FILES)
def test_every_claim_flow_references_the_canonical_rule(relative: str) -> None:
    mentions = [line for line in _read(relative).splitlines() if "evidence" in line.lower()]

    assert mentions, f"{relative} makes claims without referencing the evidence rule"
    assert any(CANONICAL_REF.search(line) for line in mentions), (
        f"{relative} mentions evidence without referencing engineering-contracts §0"
    )


@pytest.mark.parametrize("relative", REFERENCING_FILES)
def test_referencing_files_do_not_restate_the_canonical_body(relative: str) -> None:
    body = _read(relative)

    restated = [evidence_class for evidence_class in EVIDENCE_CLASSES if evidence_class in body]
    assert not restated, f"{relative} restates the evidence classes instead of referencing them: {restated}"
