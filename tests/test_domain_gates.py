"""The `domains/<slug>/gates/*.md` frontmatter contract.

`che-ship §0.9.5` parses these files to decide whether to run a gate, how to score
it, and what to log. Gate files are prompt inputs rather than code, so nothing else
enforces their shape — and the README in five domain folders instructs authors to
copy `domains/ux/gates/pixel-check-gate.md` as the pilot, which propagates any
drift to every future gate.

This caught a real instance: `pixel-check-gate.md` declared `tool_primary` /
`tool_fallback` while §0.9.5 parses `tool_official`, and named a tool signature
(`diff_jsx(file_id, node_id, actual_dom_screenshot)`) whose parameters do not exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pytest

import che_core

#: `§0.9.5` step 2 skips `engineering` entirely, so its gates are never parsed and
#: legitimately carry no frontmatter. Only the other domains are contractual.
_ENGINEERING = "engineering"

#: Keys §0.9.5 step 3.c parses. `executable` is how a gate declares that it has no
#: working mechanism yet, so ship can skip it instead of fabricating a result.
_REQUIRED_KEYS = ("retry_policy", "log_format_decisions", "tool_official", "executable")

#: A gate is only usable if it declares a numeric pass rule under one of these.
_THRESHOLD_KEYS = ("threshold_pass", "threshold_hard_stop")


def _repo_root() -> Path:
    return Path(che_core.__file__).resolve().parent.parent


def _frontmatter(path: Path) -> Dict[str, str]:
    """Parse the leading `---` block into a flat key/value map.

    Deliberately independent of `che_core.state_store._parse_spec_frontmatter`: a
    test that asserts a text contract must not lean on the code it is guarding, and
    that private helper carries spec-specific defaults this contract does not want.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out: Dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip().strip("'\"")
    return out


def _gate_files() -> List[Path]:
    domains = _repo_root() / "domains"
    return sorted(
        p for p in domains.glob("*/gates/*.md") if p.name != "README.md" and p.parent.parent.name != _ENGINEERING
    )


def test_there_is_at_least_one_gate_to_check() -> None:
    """Guard against the glob silently matching nothing and passing vacuously."""
    assert _gate_files(), "no non-engineering gate files found — did the layout move?"


@pytest.mark.parametrize("gate", _gate_files(), ids=lambda p: f"{p.parent.parent.name}/{p.name}")
def test_gate_declares_every_key_ship_parses(gate: Path) -> None:
    fm = _frontmatter(gate)

    assert fm, f"{gate} has no YAML frontmatter; §0.9.5 step 3.c fails the gate outright."
    assert any(k in fm for k in _THRESHOLD_KEYS), (
        f"{gate} declares no numeric threshold (expected one of {_THRESHOLD_KEYS}); "
        "§0.9.5 cannot evaluate a gate without one."
    )
    for key in _REQUIRED_KEYS:
        assert key in fm, f"{gate} is missing `{key}`, which §0.9.5 step 3.c parses."

    assert fm["executable"] in ("true", "false"), (
        f"{gate}: `executable` must be the literal true or false, got {fm['executable']!r}."
    )


def test_a_disabled_gate_must_declare_what_is_missing() -> None:
    """`executable: false` without a reason is indistinguishable from a pass.

    A silently skipped gate turns "never verified" into "verified", which is worse
    than having no gate at all — so a reason is mandatory, not decorative.
    """
    disabled = [g for g in _gate_files() if _frontmatter(g).get("executable") == "false"]

    for gate in disabled:
        assert _frontmatter(gate).get("blocked_by", "").strip(), (
            f"{gate} sets `executable: false` without a `blocked_by:` reason."
        )


def _headings(path: Path) -> List[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("#")]


def test_an_executable_gate_documents_the_steps_ship_follows() -> None:
    """§0.9.5 step 3.c runs "EXACTLY the steps listed in the gate's 'Execution' section".

    A gate declaring `executable: true` with no such section leaves ship with nothing
    to follow — the gate is nominally runnable and still never runs, which is the
    same end state as `executable: false` but without the honest skip.
    """
    missing = [
        gate
        for gate in _gate_files()
        if _frontmatter(gate).get("executable") == "true"
        and not any("Execution" in heading for heading in _headings(gate))
    ]

    assert not missing, f"gates declare `executable: true` with no Execution section: {missing}"


def test_an_executable_gate_does_not_also_declare_a_blocker() -> None:
    """The two declarations contradict each other; ship would skip a runnable gate."""
    contradictory = [
        gate
        for gate in _gate_files()
        if _frontmatter(gate).get("executable") == "true" and _frontmatter(gate).get("blocked_by", "").strip()
    ]

    assert not contradictory, f"gates claim `executable: true` while still declaring `blocked_by:`: {contradictory}"


def test_the_pixel_gate_names_a_runner_this_repo_actually_ships() -> None:
    """Its predecessor named a tool signature that could not exist.

    The gate was declared executable while citing `diff_jsx(file_id, node_id,
    actual_dom_screenshot)` — a signature with no such parameters — so the check is
    against the real command, not against a plausible-looking recipe.
    """
    text = (_repo_root() / "domains" / "ux" / "gates" / "pixel-check-gate.md").read_text(encoding="utf-8")

    assert "che pixel check" in text, "the Execution section must name the real runner"

    for line in text.splitlines():
        if "diff_jsx(" in line:
            assert line.lstrip().startswith(">"), (
                f"`diff_jsx` may only appear in the superseded-tool warning, never as an instruction: {line!r}"
            )
