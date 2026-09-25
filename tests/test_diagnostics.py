"""Contract tests for the diagnostics module — the shape every Che failure must have.

The catalog is only worth having if three things stay true: every entry renders completely, an
agent can branch on the code without parsing prose, and a new failure cannot be raised without
being catalogued first. The third is the one that decays on its own, so it is asserted against the
source rather than against a list someone has to remember to update.
"""

from __future__ import annotations

import ast
import json
import string
from pathlib import Path

import pytest

from che_core.diagnostics import (
    ERROR_CATALOG,
    EXIT_BOUNDARY,
    EXIT_UNEXPECTED,
    EXIT_USAGE,
    CheError,
    emit,
    fail,
    json_requested,
    unexpected,
)

CHE_ROOT = Path(__file__).resolve().parent.parent
PACKAGE = CHE_ROOT / "che_core"


def _placeholders(template: str) -> set:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def _values_for(spec) -> dict:
    """A plausible value for every placeholder the spec mentions, anywhere."""
    names: set = set()
    for text in (spec.message, spec.hint, *spec.next_actions):
        names |= _placeholders(text)
    return {name: f"<{name}>" for name in names}


# ---------------------------------------------------------------------------------------------
# Every entry renders
# ---------------------------------------------------------------------------------------------


def test_the_catalog_is_not_empty() -> None:
    assert len(ERROR_CATALOG) > 20


@pytest.mark.parametrize("code", sorted(ERROR_CATALOG))
def test_every_spec_renders_completely(code: str) -> None:
    """A template missing a value would print a placeholder marker instead of the real cause."""
    spec = ERROR_CATALOG[code]
    err = CheError(code, **_values_for(spec))

    assert "missing value(s)" not in err.message
    assert err.message
    assert "missing value(s)" not in err.hint
    for action in err.next_actions:
        assert "missing value(s)" not in action
        assert action.strip()


@pytest.mark.parametrize("code", sorted(ERROR_CATALOG))
def test_every_envelope_carries_the_contract(code: str) -> None:
    spec = ERROR_CATALOG[code]
    payload = CheError(code, **_values_for(spec)).envelope()

    assert payload["status"] == "error"
    assert payload["code"] == code
    assert payload["stage"] == spec.stage
    assert isinstance(payload["retryable"], bool)
    assert isinstance(payload["next_actions"], list)
    assert payload["exit_code"] == spec.exit_code


def test_codes_carry_identity_where_exit_numbers_cannot() -> None:
    """The reason this module exists: many failures share exit 2, so the number cannot branch."""
    by_number: dict = {}
    for spec in ERROR_CATALOG.values():
        by_number.setdefault(spec.exit_code, []).append(spec.code)

    overloaded = {number: codes for number, codes in by_number.items() if len(codes) > 1}
    assert overloaded, "if no exit code were shared, the string codes would be redundant"
    assert len(overloaded[EXIT_USAGE]) > 5


# ---------------------------------------------------------------------------------------------
# Rendering, in both shapes
# ---------------------------------------------------------------------------------------------


def test_human_output_names_the_cause_the_remedy_and_the_command(capsys) -> None:
    err = CheError("UNKNOWN_PROJECT", project_slug="acme")

    code = emit(err, json_mode=False)

    captured = capsys.readouterr()
    assert code == err.exit_code
    assert "acme" in captured.err
    assert "Hint:" in captured.err
    assert "Next: che project init" in captured.err
    assert captured.out == "", "human mode must not write to stdout"


def test_json_output_lands_on_stdout_so_a_caller_always_finds_it(capsys) -> None:
    err = CheError("UNKNOWN_PROJECT", project_slug="acme")

    emit(err, json_mode=True)

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["code"] == "UNKNOWN_PROJECT"
    assert payload["details"] == {"project_slug": "acme"}
    assert captured.err == ""


def test_an_uncatalogued_code_says_so_rather_than_failing_differently() -> None:
    err = CheError("NO_SUCH_CODE")

    assert err.exit_code == EXIT_UNEXPECTED
    assert "not in ERROR_CATALOG" in "\n".join(err.human_lines())
    assert err.envelope()["status"] == "error"


def test_a_template_missing_a_value_still_reports_the_failure() -> None:
    """Losing the message would be worse than losing the value that was meant to be in it."""
    err = CheError("UNKNOWN_PROJECT")

    assert "project_slug" in err.message
    assert "missing value(s)" in err.message


def test_unexpected_keeps_the_exception_type_visible() -> None:
    err = unexpected(KeyError("boom"))

    assert err.code == "UNEXPECTED"
    assert "KeyError" in err.message
    assert "boom" in err.message
    assert "Che bug" in err.hint


def test_fail_raises_rather_than_prints() -> None:
    with pytest.raises(CheError) as raised:
        fail("MISSING_WORKTREE_ROOT")

    assert raised.value.code == "MISSING_WORKTREE_ROOT"
    assert raised.value.exit_code == EXIT_USAGE


def test_the_boundary_violation_keeps_its_own_exit_code() -> None:
    err = CheError("STORAGE_BOUNDARY_VIOLATION", label="decisions.log", path="/repo/decisions.log")

    assert err.exit_code == EXIT_BOUNDARY


def test_json_requested_reads_the_flag_from_the_command_line() -> None:
    assert json_requested(["project", "list", "--json"]) is True
    assert json_requested(["--json", "project", "list"]) is True
    assert json_requested(["project", "list"]) is False


# ---------------------------------------------------------------------------------------------
# The guard: a failure cannot be raised without being catalogued first
# ---------------------------------------------------------------------------------------------


def _raised_at_call_sites(source: Path) -> list:
    """Every literal code raised in one module, with the keywords that site actually passes.

    A site that splats ``**values`` cannot be read statically, so it is skipped: a test can only
    promise what it can see.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    sites: list = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name not in {"fail", "CheError"}:
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            continue
        if any(keyword.arg is None for keyword in node.keywords):
            continue
        sites.append((first.value, tuple(sorted(kw.arg for kw in node.keywords)), node.lineno))
    return sites


def _called_codes(source: Path) -> set:
    """Every literal code passed to `fail(...)` or `CheError(...)` in one module."""
    return {code for code, _, _ in _raised_at_call_sites(source)}


def test_every_code_raised_in_the_package_is_catalogued() -> None:
    """`ERROR_CATALOG` is the source of truth, so it has to be edited before the call site.

    Asserted against the source because a list kept by hand drifts; this fails the moment someone
    raises a code the catalog does not describe.
    """
    uncatalogued: dict = {}
    for source in sorted(PACKAGE.rglob("*.py")):
        if source.name == "diagnostics.py":
            continue
        unknown = sorted(_called_codes(source) - set(ERROR_CATALOG))
        if unknown:
            uncatalogued[str(source.relative_to(CHE_ROOT))] = unknown

    assert not uncatalogued, f"codes raised but not in ERROR_CATALOG: {uncatalogued}"


def test_every_code_renders_with_only_the_values_its_call_site_passes() -> None:
    """A spec may not ask for a value the site raising it cannot supply.

    `test_every_spec_renders_completely` renders each spec with a value for every placeholder it
    mentions, which is exactly why `DESIGN_TREE_MISSING` kept asking for a `sub_product` that
    `che designer tokens render` has no way to know: the spec was checked against itself, never
    against its callers. This renders from the other end — with what each site actually passes.
    """
    incomplete: list = []
    for source in sorted(PACKAGE.rglob("*.py")):
        if source.name == "diagnostics.py":
            continue
        for code, keywords, line in _raised_at_call_sites(source):
            err = CheError(code, **{name: f"<{name}>" for name in keywords})
            rendered = [err.message, err.hint, *err.next_actions]
            if any("missing value(s)" in text for text in rendered):
                site = f"{source.relative_to(CHE_ROOT)}:{line} {code} (passes: {', '.join(keywords) or 'nothing'})"
                incomplete.append(site)

    assert not incomplete, "specs asking for values their call site cannot pass:\n" + "\n".join(incomplete)
