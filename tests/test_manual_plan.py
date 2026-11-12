"""Contract tests for the manual test plan's executable blocks.

The plan is the one artifact that reaches the human tester, the agent executor and the PR body, so
these assertions guard the three things that make it executable: the restricted parser, the MP-gate,
and ``sync`` never inventing content.
"""

from __future__ import annotations

from pathlib import Path

from che_core.manual_plan import parse_contract, sync_plan, validate_plan

CONTRACT = """\
# --- executable contract (AC-1) ---
id: AC-1
driver: ui
lane: local
base_url: http://localhost:3000
evidence: [screenshot, console_log]
severity: HIGH
steps:
  - action: goto
    url: /bookings/B-1001
    expect_visible: Paid
  - action: click
    role: button
    name: Process refund
  - action: fill
    label: Amount
    value: "10.00"
  - action: assert
    expect_visible: Refunded
    expect_api: GET /api/bookings/B-1001 200
"""

PLAN = f"""\
# Manual Test Plan — refunds

## 1. Per Acceptance Criterion

### AC-1: Process a refund on a paid booking

**GIVEN:** a paid booking
**WHEN:** the ops user processes a refund
**THEN:** the booking shows Refunded

```yaml
{CONTRACT}```

#### Severity if FAILS

- HIGH
"""

LEGACY_PLAN = """\
# Manual Test Plan — legacy

## 1. Per Acceptance Criterion

### AC-1: Process a refund on a paid booking

**GIVEN:** a paid booking
**WHEN:** the ops user processes a refund
**THEN:** the booking shows Refunded

#### Manual Steps

1. Open the booking
2. Click Process refund
"""


def _plan_with(contract: str) -> str:
    return PLAN.replace(CONTRACT, contract)


# --- Parser ------------------------------------------------------------------


def test_parser_reads_steps_and_inline_lists():
    contract, problems = parse_contract(CONTRACT)

    assert problems == []
    assert contract["driver"] == "ui"
    assert contract["evidence"] == ["screenshot", "console_log"]
    assert contract["steps"][1] == {"action": "click", "role": "button", "name": "Process refund"}
    assert contract["steps"][2]["value"] == "10.00"


def test_parser_strips_comments_outside_quotes():
    contract, problems = parse_contract('id: AC-1  # the heading\nlane: "local # not a comment"\n')

    assert problems == []
    assert contract["id"] == "AC-1"
    assert contract["lane"] == "local # not a comment"


def test_parser_reports_a_list_item_outside_steps():
    _contract, problems = parse_contract("- action: goto\n")

    assert problems and "only valid under `steps:`" in problems[0]


# --- Gate --------------------------------------------------------------------


def test_a_complete_plan_passes(tmp_path):
    plan = tmp_path / "manual_test_plan.md"
    plan.write_text(PLAN, encoding="utf-8")

    report = validate_plan(str(plan))

    assert report["ok"] is True, report["failures"]
    assert report["acs"] == 1


def test_an_ac_without_a_contract_fails(tmp_path):
    plan = tmp_path / "manual_test_plan.md"
    plan.write_text(LEGACY_PLAN, encoding="utf-8")

    report = validate_plan(str(plan))

    assert report["ok"] is False
    assert any("no ```yaml executable contract block" in failure for failure in report["failures"])


def test_a_css_locator_is_rejected(tmp_path):
    plan = tmp_path / "manual_test_plan.md"
    plan.write_text(
        _plan_with(CONTRACT.replace("role: button\n    name: Process refund", "css: button.refund")), "utf-8"
    )

    report = validate_plan(str(plan))

    assert report["ok"] is False
    assert any("CSS/XPath locators are not allowed" in failure for failure in report["failures"])


def test_a_weasel_assertion_is_rejected(tmp_path):
    plan = tmp_path / "manual_test_plan.md"
    plan.write_text(_plan_with(CONTRACT.replace("expect_visible: Refunded", "expect_visible: works")), "utf-8")

    report = validate_plan(str(plan))

    assert report["ok"] is False
    assert any("weasel word" in failure for failure in report["failures"])


def test_a_manual_driver_cannot_claim_browser_steps(tmp_path):
    plan = tmp_path / "manual_test_plan.md"
    plan.write_text(_plan_with(CONTRACT.replace("driver: ui", "driver: manual")), "utf-8")

    report = validate_plan(str(plan))

    assert report["ok"] is False
    assert any("driver=manual requires every step" in failure for failure in report["failures"])


def test_an_api_driver_needs_an_api_step(tmp_path):
    plan = tmp_path / "manual_test_plan.md"
    plan.write_text(
        _plan_with(CONTRACT.replace("driver: ui", "driver: api").replace("base_url: http://localhost:3000", "")),
        "utf-8",
    )

    report = validate_plan(str(plan))

    assert report["ok"] is False
    assert any("driver=api requires at least one" in failure for failure in report["failures"])


def test_an_unknown_step_key_is_a_typo_not_a_silent_pass(tmp_path):
    plan = tmp_path / "manual_test_plan.md"
    plan.write_text(_plan_with(CONTRACT.replace("expect_visible: Refunded", "expect_visble: Refunded")), "utf-8")

    report = validate_plan(str(plan))

    assert report["ok"] is False
    assert any("unknown key(s) expect_visble" in failure for failure in report["failures"])


def test_a_plan_with_no_acs_fails(tmp_path):
    plan = tmp_path / "manual_test_plan.md"
    plan.write_text("# nothing here\n", encoding="utf-8")

    report = validate_plan(str(plan))

    assert report["ok"] is False
    assert report["failures"] == ["MP1: no `### AC-<N>:` headings"]


# --- Scaffold / migrate ------------------------------------------------------


def test_sync_creates_a_plan_that_is_honest_about_being_unfinished(bound_worktree):
    repo, paths = bound_worktree

    result = sync_plan(str(repo), "test-session")

    assert result["created"] is True
    plan = Path(result["path"])
    assert plan.is_file()
    assert str(paths["CHE_WORKSPACE_SHARED"]) in str(plan)
    report = validate_plan(str(plan))
    assert report["ok"] is False, "a TODO skeleton must not pass the gate"


def test_sync_migrates_a_legacy_plan_and_preserves_the_prose(bound_worktree):
    repo, paths = bound_worktree
    plan = Path(paths["CHE_WORKSPACE_SHARED"]) / "manual_test_plan.md"
    plan.write_text(LEGACY_PLAN, encoding="utf-8")

    result = sync_plan(str(repo), "test-session")

    assert result["path"] == str(plan)
    assert result["inserted"] == ["AC-1"]
    text = plan.read_text(encoding="utf-8")
    assert "```yaml" in text
    assert "#### Manual Steps" in text
    assert "2. Click Process refund" in text


def test_sync_is_idempotent(bound_worktree):
    repo, paths = bound_worktree
    plan = Path(paths["CHE_WORKSPACE_SHARED"]) / "manual_test_plan.md"
    plan.write_text(LEGACY_PLAN, encoding="utf-8")

    sync_plan(str(repo), "test-session")
    second = sync_plan(str(repo), "test-session")

    assert second["changed"] is False
    assert second["inserted"] == []


def test_sync_dry_run_writes_nothing(bound_worktree):
    repo, _paths = bound_worktree

    result = sync_plan(str(repo), "test-session", dry_run=True)

    assert result["created"] is True
    assert not Path(result["path"]).exists()


def test_sync_never_touches_an_existing_contract(bound_worktree):
    repo, paths = bound_worktree
    plan = Path(paths["CHE_WORKSPACE_SHARED"]) / "manual_test_plan.md"
    plan.write_text(PLAN, encoding="utf-8")

    result = sync_plan(str(repo), "test-session")

    assert result["changed"] is False
    assert plan.read_text(encoding="utf-8") == PLAN


# --- Documentation contracts -------------------------------------------------

CHE_ROOT = Path(__file__).resolve().parent.parent


def _read(relative: str) -> str:
    return (CHE_ROOT / relative).read_text(encoding="utf-8")


def test_the_command_invokes_the_skill():
    assert "che-manual-plan" in _read("commands/che-manual-plan.md")


def test_the_executor_runs_on_chrome_devtools_and_the_terminal_only():
    executor = _read("skills/che-manual-test-executor/SKILL.md")

    assert "Chrome DevTools MCP" in executor
    assert "take_snapshot" in executor
    assert "Playwright" not in executor
    assert "playwright" not in executor


def test_the_executor_refuses_a_plan_that_fails_the_gate():
    assert "che manual-plan validate" in _read("skills/che-manual-test-executor/SKILL.md")


def test_che_commands_lists_the_new_command():
    commands = _read("CHE_COMMANDS.md")

    assert "| `/che-manual-plan" in commands
    assert "## `/che-manual-plan" in commands
    assert "Chrome DevTools MCP" in commands
