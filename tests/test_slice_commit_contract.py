"""Contract test for the slice-commit + review-mode rules.

1 vertical slice = 1 commit is a process rule: if the anchors disappear nothing fails at runtime, the
commits drift back into a single ship-time batch and the per-slice human gate silently vanishes. These
assertions pin the contract across che-act, che-developer, che-ship, the envelope template and the
Paperclip mirror.
"""

from __future__ import annotations

from pathlib import Path

import pytest

CHE_ROOT = Path(__file__).resolve().parent.parent

ACT = "skills/che-act/SKILL.md"
DEVELOPER = "skills/che-developer/SKILL.md"
SHIP = "skills/che-ship/SKILL.md"
ENVELOPE = "skills/che-act/references/TASK_ENVELOPE_TEMPLATE.md"

#: Anchors each file must keep, keyed by relative path.
ANCHORS = {
    ACT: [
        "REVIEW_MODE",
        "INCREMENTAL",
        "FINAL",
        "SLICE REVIEW REPORT",
        "SLICE COMMIT CONTRACT",
        "1 vertical slice = 1 commit",
        "SLICE_COMMIT_DEFERRED_PARALLEL",
        "REVIEW_MODE_OVERRIDE",
    ],
    DEVELOPER: [
        "Slice commit — 1 slice = 1 commit",
        "SLICE_COMMIT",
        "NEVER** `git add .`",
    ],
    SHIP: ["SLICE COMMITS ALREADY EXIST", "DO NOT re-group"],
    ENVELOPE: ["Review mode", "exactly ONE conventional commit"],
}

#: Files that must keep the slice-commit rule wired into their decision point.
WIRING = {
    "CHE_RULES.md": "never re-grouped or squashed",
    "paperclip/package/skills/che-act/SKILL.md": "SLICE REVIEW REPORT",
    "paperclip/package/skills/che-developer/SKILL.md": "SLICE_COMMIT",
}


def _read(relative: str) -> str:
    return (CHE_ROOT / relative).read_text(encoding="utf-8")


@pytest.mark.parametrize("relative,anchor", [(f, a) for f, anchors in ANCHORS.items() for a in anchors])
def test_slice_commit_contract_keeps_its_anchors(relative: str, anchor: str) -> None:
    assert anchor in _read(relative), f"{relative} lost the contract anchor: {anchor!r}"


@pytest.mark.parametrize("relative,fragment", WIRING.items())
def test_slice_commit_rule_is_wired(relative: str, fragment: str) -> None:
    assert fragment in _read(relative), f"{relative} no longer references {fragment!r}"
