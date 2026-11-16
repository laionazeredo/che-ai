"""Tests for the executable SPEC gates: ``che spec validate`` / ``coverage`` / ``merge``.

The checks used to live only as prose in ``skills/che-spec/SKILL.md``. These tests
pin the behaviour that replaced them: a valid draft passes, each structural defect
fails with its own V-id, the tier decides which gates apply, and the as-built merge
never loses a behaviour it already knew.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from che_core.spec import coverage, infer_tier, merge_as_built, parse_frontmatter, validate_spec
from che_core.workspaces import init_project

WORKTREE = Path(__file__).resolve().parents[1]


def _spec(
    *,
    b_rows: str = "| B-1 | given one | when one | Then HTTP 201 · row created | [✅Integ] | | 95% | none |\n"
    "| B-2 | given two | when two | Then row count == 2 | [✅Unit] | | 90% | none |",
    ab_rows: str = "| AB-1 | given one | when duplicate | Then DOES NOT create a second row | [✅Integ] | | 99% | none |",
    slices: str = (
        "| **F0** | tracer | **B-1**, B-2, AB-1 | `pages/x` · `app/api/y` | one test per layer "
        "| Creator clicks Save and row 1 shows the new title |"
    ),
    files: int = 8,
    risk: str = "low",
    with_slices: bool = True,
    with_alternatives: bool = True,
    with_kill: bool = True,
    tier: str = "",
    frontmatter_extra: str = "",
    s4_head: str = "",
    s4_extra: str = "",
) -> str:
    alternatives = (
        "- Alternatives considered: reuse the existing endpoint (rejected: wrong auth scope)\n"
        if with_alternatives
        else ""
    )
    kill = "- Kill criterion: abandon if the p95 latency exceeds 300 ms after two attempts\n" if with_kill else ""
    tier_line = f"spec_tier: {tier}\n" if tier else ""
    slice_block = (
        f"### §4.5 VERTICAL SLICES\n\n| Slice ID | Name | B-IDs | Layers | Tests | DONE |\n|---|---|---|---|---|---|\n{slices}\n\n"
        if with_slices
        else ""
    )
    return f"""---
spec_id: demo
ticket_ref: NONE
worktree_root: /tmp/demo
change_class: feature
domain: engineering
risk_level: {risk}
status: Draft
readiness: passed
readiness_report: /tmp/readiness.md
open_assumptions: []
estimated_files_max: {files}
{tier_line}{frontmatter_extra}---

## §0 EXECUTIVE SUMMARY (read this first)

| Field | Content |
|---|---|
| What changes | the user can save a row |
| Decisions needed from you | none |

## §1 WHY (Problem Statement)

- Current: rows cannot be saved
- Goal: save a row — simplest option is the existing endpoint
- Non-goals (deferred by design): bulk import
{alternatives}{kill}
## §2 SCOPE BOUNDARIES & BLAST RADIUS

### ✅ CAN TOUCH (<=10 files)

- `pages/x.tsx`
- `app/api/y.ts`

## §3 CONTRACTS (Design by Contract)

### PREconditions (before start)

- worktree bound

### POSTconditions (after all tasks DONE)

- POST returns 201

### INVARIANTS (never break)

- INV-1: untouched files stay byte-identical

## §4 SPECIFICATION BY EXAMPLE

{s4_head}### §4.2 POSITIVE BEHAVIOUR EXAMPLES

| B-ID | Given | When | Then | Test Layers | UI Selector | Confidence | Risk |
|---|---|---|---|---|---|---|---|
{b_rows}

### §4.3 ANTI-BEHAVIOUR EXAMPLES

| AB-ID | Given | When | Then PROHIBITED | Test Layers | UI Selector | Confidence | Risk |
|---|---|---|---|---|---|---|---|
{ab_rows}

{s4_extra}{slice_block}## §5 VERIFICATION MATRIX

| Anchor | Status | Test file |
|---|---|---|
| B-1 | Planned | tests/test_demo.py |
"""


def _write(tmp_path: Path, text: str, name: str = "spec.md") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_spec_passes_every_applicable_check(tmp_path: Path) -> None:
    report = validate_spec(str(_write(tmp_path, _spec())))

    assert report["ok"] is True, report["failures"]
    assert report["tier"] == "standard"
    assert report["counts"] == {"b": 2, "ab": 1}


def test_missing_anti_behaviour_fails_v10(tmp_path: Path) -> None:
    report = validate_spec(str(_write(tmp_path, _spec(ab_rows=""))))

    assert report["ok"] is False
    assert any(failure.startswith("V10:") for failure in report["failures"])


def test_more_than_ten_behaviours_fails_v9(tmp_path: Path) -> None:
    rows = "\n".join(
        f"| B-{index} | given | when | Then value == {index} | [✅Unit] | | 90% | none |" for index in range(1, 12)
    )
    report = validate_spec(str(_write(tmp_path, _spec(b_rows=rows))))

    assert report["ok"] is False
    assert any(failure.startswith("V9:") for failure in report["failures"])


def test_lite_tier_skips_the_vertical_slice_gate(tmp_path: Path) -> None:
    text = _spec(with_slices=False, files=3, tier="lite")
    report = validate_spec(str(_write(tmp_path, text)))

    statuses = {entry["id"]: entry["status"] for entry in report["checks"]}
    assert statuses["V16"] == "skip"
    assert report["ok"] is True, report["failures"]


def test_weasel_done_criterion_fails_v16(tmp_path: Path) -> None:
    slices = "| **F0** | tracer | **B-1** | `pages/x` · `app/api/y` | test | it works correctly |"
    report = validate_spec(str(_write(tmp_path, _spec(slices=slices))))

    assert report["ok"] is False
    assert any(failure.startswith("V16:") for failure in report["failures"])


def test_tier_is_inferred_from_risk_and_blast_radius() -> None:
    assert infer_tier({"risk_level": "low", "estimated_files_max": "3"}) == "lite"
    assert infer_tier({"risk_level": "low", "estimated_files_max": "8"}) == "standard"
    assert infer_tier({"risk_level": "high", "estimated_files_max": "3"}) == "full"
    assert infer_tier({"risk_level": "low", "estimated_files_max": "3", "spec_tier": "full"}) == "full"


def test_frontmatter_parser_handles_inline_lists() -> None:
    frontmatter, body = parse_frontmatter("---\nkey: [a, b]\nflag: true\n---\nbody\n")

    assert frontmatter == {"key": ["a", "b"], "flag": "true"}
    assert body.strip() == "body"


def test_coverage_names_the_anchors_no_test_mentions(tmp_path: Path) -> None:
    spec = _write(tmp_path, _spec())
    worktree = tmp_path / "wt"
    (worktree / "tests").mkdir(parents=True)
    (worktree / "tests" / "test_demo.py").write_text("def test_it():\n    assert 'B-1' in 'B-1'\n", encoding="utf-8")

    report = coverage(str(spec), worktree=str(worktree))

    statuses = {row["anchor"]: row["status"] for row in report["rows"]}
    assert statuses == {"B-1": "covered", "B-2": "missing", "AB-1": "missing"}
    assert report["ok"] is False


def test_merge_keeps_previous_behaviours_and_reports_the_delta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARNESS_SESSIONS_ROOT", raising=False)
    monkeypatch.setenv("CHE_WORKSPACES_ROOT", str(tmp_path / "che-workspaces"))
    worktree = tmp_path / "wt"
    worktree.mkdir()

    first = _spec().replace("/tmp/demo", str(worktree))
    first_path = _write(tmp_path, first, "first.md")
    merge_as_built(str(first_path), "acme", domain="engineering", dry_run=False)

    second = _spec().replace("/tmp/demo", str(worktree)).replace("row count == 2", "row count == 3")
    second = second.replace("spec_id: demo", "spec_id: demo-v2")
    second_path = _write(tmp_path, second, "second.md")
    result = merge_as_built(str(second_path), "acme", domain="engineering", dry_run=False)

    assert result["added"] == []
    assert result["modified"] == ["B-2"]
    target = Path(result["target"])
    content = target.read_text(encoding="utf-8")
    assert "B-1" in content and "B-2" in content
    assert "row count == 3" in content


def test_cli_validate_exits_one_on_failure(tmp_path: Path) -> None:
    broken = _write(tmp_path, _spec(ab_rows=""))

    result = subprocess.run(
        [sys.executable, "-m", "che_core.cli", "spec", "validate", str(broken), "--json"],
        cwd=str(WORKTREE),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(WORKTREE)},
    )

    assert result.returncode == 1
    assert '"ok": false' in result.stdout


def test_project_init_writes_the_constitution_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARNESS_SESSIONS_ROOT", raising=False)
    monkeypatch.setenv("CHE_WORKSPACES_ROOT", str(tmp_path / "che-workspaces"))

    first = init_project(str(WORKTREE), slug="acme", domain="engineering")
    constitution = Path(first["project_dir"]) / "constitution.md"
    assert constitution.is_file()
    assert "Simplicity first" in constitution.read_text(encoding="utf-8")

    second = init_project(str(WORKTREE), slug="acme", domain="engineering")
    assert str(constitution) not in second["files_created"]


# --- State model (V27 / V28) -------------------------------------------------

STATE_MODEL = """### §4.4.2 STATE MODEL

**Initial:** `pending`
**Terminal:** `refunded`

| State | Event | Guard | Next | Legal? | Ref |
|---|---|---|---|---|---|
| pending | payment.captured | amount > 0 | paid | yes | B-1 |
| pending | payment.captured | amount == 0 | pending | no | AB-1 |
| paid | refund.requested | — | refunded | yes | B-2 |

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> paid: payment.captured (B-1)
    paid --> refunded: refund.requested (B-2)
    refunded --> [*]
```

"""

TRACE = """### §4.0 TICKET TRACEABILITY

| Ticket AC | B-IDs | Status | Why not covered |
|---|---|---|---|
| AC-1 save a row | B-1, B-2 | covered | — |

"""


def _statuses(report: dict) -> dict:
    return {entry["id"]: entry["status"] for entry in report["checks"]}


def test_a_complete_state_model_passes(tmp_path: Path) -> None:
    text = _spec(frontmatter_extra="stateful_entity: true\n", s4_extra=STATE_MODEL)

    report = validate_spec(str(_write(tmp_path, text)))

    assert report["ok"] is True, report["failures"]
    assert _statuses(report)["V27"] == "pass"
    assert _statuses(report)["V28"] == "pass"


def test_stateful_entity_without_a_model_fails_v27(tmp_path: Path) -> None:
    report = validate_spec(str(_write(tmp_path, _spec(frontmatter_extra="stateful_entity: true\n"))))

    assert any(failure.startswith("V27:") for failure in report["failures"])


def test_forbidden_transition_must_reference_an_ab_id(tmp_path: Path) -> None:
    broken = STATE_MODEL.replace(
        "| pending | payment.captured | amount == 0 | pending | no | AB-1 |",
        "| pending | payment.captured | amount == 0 | pending | no | B-1 |",
    )

    report = validate_spec(str(_write(tmp_path, _spec(s4_extra=broken))))

    assert any("forbidden transition must reference an AB-ID" in failure for failure in report["failures"])


def test_unreachable_state_fails_v27(tmp_path: Path) -> None:
    broken = STATE_MODEL.replace("**Terminal:** `refunded`", "**Terminal:** `refunded`, `cancelled`").replace(
        "| paid | refund.requested | — | refunded | yes | B-2 |",
        "| paid | refund.requested | — | refunded | yes | B-2 |\n"
        "| cancelled | refund.requested | — | cancelled | yes | B-2 |",
    )

    report = validate_spec(str(_write(tmp_path, _spec(s4_extra=broken))))

    assert any("unreachable state(s)" in failure for failure in report["failures"])


def test_a_state_model_needs_its_rendering(tmp_path: Path) -> None:
    broken = STATE_MODEL.split("```mermaid")[0]

    report = validate_spec(str(_write(tmp_path, _spec(s4_extra=broken))))

    assert any("stateDiagram-v2" in failure for failure in report["failures"])


# --- Traceability (V29), slice coverage (V30), counter drift (V31) -----------


def test_a_ticket_ref_requires_a_traceability_table(tmp_path: Path) -> None:
    report = validate_spec(str(_write(tmp_path, _spec(frontmatter_extra="ticket_ref: AT-352\n"))))

    assert any(failure.startswith("V29:") for failure in report["failures"])


def test_a_traceability_row_must_be_complete(tmp_path: Path) -> None:
    broken = TRACE.replace(
        "| AC-1 save a row | B-1, B-2 | covered | — |", "| AC-1 save a row | B-1, B-9 | covered | — |"
    )

    report = validate_spec(str(_write(tmp_path, _spec(frontmatter_extra="ticket_ref: AT-352\n", s4_head=broken))))

    assert any("B-9 is not declared" in failure for failure in report["failures"])


def test_a_complete_traceability_table_passes(tmp_path: Path) -> None:
    report = validate_spec(str(_write(tmp_path, _spec(frontmatter_extra="ticket_ref: AT-352\n", s4_head=TRACE))))

    assert _statuses(report)["V29"] == "pass"


def test_a_behaviour_missing_from_every_slice_fails_v30(tmp_path: Path) -> None:
    slices = "| **F0** | tracer | **B-1** | `pages/x` · `app/api/y` | one test | Creator sees the row |"

    report = validate_spec(str(_write(tmp_path, _spec(slices=slices))))

    assert any("never placed in a §4.5 slice" in failure for failure in report["failures"])


def test_a_declared_counter_must_match_the_body(tmp_path: Path) -> None:
    report = validate_spec(str(_write(tmp_path, _spec(frontmatter_extra="b_count: 9\n"))))

    assert any(failure.startswith("V31:") for failure in report["failures"])


def test_a_tracer_flag_must_match_the_f0_row(tmp_path: Path) -> None:
    report = validate_spec(str(_write(tmp_path, _spec(frontmatter_extra="tracer_f0_defined: false\n"))))

    assert any("tracer_f0_defined=false" in failure for failure in report["failures"])


def test_an_approved_spec_is_not_re_judged_on_planning_completeness(tmp_path: Path) -> None:
    text = _spec(frontmatter_extra="status: Approved\nticket_ref: AT-352\n")

    report = validate_spec(str(_write(tmp_path, text)))

    assert _statuses(report)["V29"] == "skip"
    assert report["ok"] is True, report["failures"]
