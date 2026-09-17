"""Contract tests for `che_core/pixel_dom.py` — the implementation-side fact bag.

The bag is the one input to this gate that a person or an agent assembles, and every
defect this module exists to catch is a *shape* defect: the numbers are real measurements
and the bag is wrong about what they mean. Neither defect announces itself. A `line_height`
of 24 where §1 #8 compares a multiplier is scored as a 22.5-unit deviation — a confident
failure for a mistake in the caller; and a selector the map names but the bag omits is
scored as `missing_from_dom` — a *failure* attributed to an element nobody measured.

So the tests come in three groups, and the second is not padding. A validator stricter
than the comparator relocates the same mistake one level down: it refuses to score a run
whose numbers were fine. Group three is the coupling — the contract must not fall behind
`CATEGORIES`, and it must not invent a property the engine never reads.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from che_core.pixel import CATEGORIES
from che_core.pixel_dom import (
    CHECKED_PROPERTIES,
    SHADOW_AXES,
    _is_number_list,
    fact_bag_summary,
    summarise_problems,
    validate_dom_facts,
)

CHE_CLI_CMD = [sys.executable, "-m", "che_core.cli"]


def _record(**overrides) -> dict:
    """The smallest record the contract accepts, plus whatever this test is about."""
    record: dict = {"coord_frame": "viewport"}
    record.update(overrides)
    return record


def _problems(record: dict) -> list:
    return validate_dom_facts({"#hero": record}, ["#hero"])


# --- Group 1: shapes the contract must refuse --------------------------------


def test_a_pixel_line_height_is_refused_as_a_unit_mistake() -> None:
    """The defect that motivated the module: 24 is the browser's px reading, not the ratio.

    §1 #8 compares `1.5` against `1.5`. Handing over `24` does not produce a missing
    measurement — it produces a large, confident deviation, so the run's only clue that the
    caller was mistaken is a score that looks like a design problem.
    """
    problems = _problems(_record(line_height=24))

    assert len(problems) == 1
    assert "normalised multiplier" in problems[0]
    assert _problems(_record(line_height=1.5)) == []


@pytest.mark.parametrize("value", [0.4, 5.1])
def test_a_line_height_outside_the_ratio_band_is_refused(value: float) -> None:
    assert "normalised multiplier" in _problems(_record(line_height=value))[0]


def test_a_pixel_letter_spacing_is_refused_as_a_unit_mistake() -> None:
    """#9's tolerance is 0.01**em**; a px reading is two orders of magnitude outside it."""
    assert "must be em" in _problems(_record(letter_spacing=1.0))[0]
    # The band is wide enough to admit a real design's tightest and loosest tracking.
    assert _problems(_record(letter_spacing=-0.02)) == []
    assert _problems(_record(letter_spacing=0.05)) == []


def test_a_selector_the_map_names_but_the_bag_omits_is_refused() -> None:
    """The highest-value check here: the comparator cannot tell an omission from a miss.

    `join_by_map` reads an absent selector as `missing_from_dom`, which is a finding about
    the implementation. It is not — it is an extraction that was never attempted, and
    letting it through fails the run on an element the gate never looked at.
    """
    problems = validate_dom_facts({"#hero": _record()}, ["#hero", "#cta"])

    assert len(problems) == 1
    assert problems[0].startswith("#cta:")
    assert "missing_from_dom" in problems[0]


def test_a_selector_the_map_repeats_is_reported_once() -> None:
    """The map is keyed by element name, so the same selector can legitimately appear twice."""
    problems = validate_dom_facts({"#hero": _record()}, ["#cta", "#cta", "#cta"])

    assert len(problems) == 1


def test_a_bag_that_is_not_an_object_is_refused_at_the_root() -> None:
    assert "keyed by selector" in validate_dom_facts([], ["#hero"])[0]


def test_a_record_that_is_not_an_object_is_refused() -> None:
    """`null` is how a hand-written bag most often expresses "not collected"."""
    problems = validate_dom_facts({"#hero": None}, ["#hero"])

    assert len(problems) == 1
    assert "expected an object of facts" in problems[0]


def test_coord_frame_is_mandatory_and_kind_is_not() -> None:
    """§2.3: only `coord_frame` changes a comparison, so only it is a precondition.

    `kind` is recorded provenance. The applicability rule that keeps a frame's absent font
    from escalating INCONCLUSIVE reads the *design* node's kind, so demanding it here would
    add a precondition that cannot alter a single measurement.
    """
    assert "coord_frame" in _problems({"kind": "frame"})[0]
    assert _problems({"coord_frame": "viewport"}) == []
    assert _problems(_record(kind="frame")) == []


def test_a_present_but_empty_kind_is_refused() -> None:
    assert "non-empty string" in _problems(_record(kind="  "))[0]


def test_shadow_must_carry_exactly_the_five_axes() -> None:
    partial = {"x": 0.0, "y": 2.0, "blur": 8.0, "spread": 0.0}
    problems = _problems(_record(shadow=partial))

    assert len(problems) == 1
    assert "alpha" in problems[0]
    assert _problems(_record(shadow={**partial, "alpha": 0.08})) == []


def test_a_shadow_axis_that_is_not_a_number_is_refused() -> None:
    whole = {axis: 0.0 for axis in SHADOW_AXES}

    assert "values must be numbers" in _problems(_record(shadow={**whole, "blur": "8px"}))[0]


@pytest.mark.parametrize("value", ["nope", "0" * 63, "A" * 64, "0" * 65])
def test_an_asset_digest_must_be_64_lowercase_hex(value: str) -> None:
    """#17 is exact, so the digest's own shape is the only thing standing between a
    mistyped reference and a category that always fails."""
    assert "64 lowercase hex" in _problems(_record(asset_sha256=value))[0]


def test_a_valid_asset_digest_is_accepted() -> None:
    assert _problems(_record(asset_sha256="a" * 64)) == []


@pytest.mark.parametrize("value", [-0.1, 1.1, "0.5"])
def test_opacity_outside_the_unit_interval_is_refused(value) -> None:
    assert "between 0 and 1" in _problems(_record(opacity=value))[0]


@pytest.mark.parametrize("value", [0, -1, 1.5, True])
def test_line_count_must_be_a_positive_integer(value) -> None:
    assert "positive integer" in _problems(_record(line_count=value))[0]


def test_a_paint_that_is_neither_colour_nor_gradient_is_refused() -> None:
    problems = _problems(_record(fg="url(#hero-pattern)"))

    assert len(problems) == 1
    assert "neither a readable colour nor a gradient" in problems[0]


@pytest.mark.parametrize("weight", [0, 1001, "bold"])
def test_font_weight_must_be_the_numeric_weight(weight) -> None:
    """The design side reports 600; the DOM side reports "bold" or "normal" unless the
    extractor maps it, and `600 != "bold"` is a mismatch rather than a parse failure."""
    assert "numeric weight" in _problems(_record(font_weight=weight))[0]


# --- Group 2: shapes the contract must not refuse ----------------------------


@pytest.mark.parametrize("padding", [8, 8.0, [8.0], (8.0, 16.0), [8.0, 16.0, 8.0, 16.0]])
def test_the_shapes_the_comparator_absorbs_are_all_accepted(padding) -> None:
    """`che_core.pixel._as_list` broadcasts a bare number and expands the CSS shorthand.

    Each of these is compared correctly by the engine, so refusing one would not protect a
    comparison — it would refuse a run whose numbers were never in question.
    """
    assert _problems(_record(padding=padding)) == []


@pytest.mark.parametrize("padding", [[1.0, 2.0, 3.0], [[1.0]], ["8px"], [1.0, None]])
def test_a_padding_the_comparator_cannot_absorb_is_refused(padding) -> None:
    assert "1, 2 or 4 px numbers" in _problems(_record(padding=padding))[0]


@pytest.mark.parametrize("gap", [16, [16.0], [16.0, 24.0]])
def test_a_two_axis_gap_is_measured_by_its_own_rule(gap) -> None:
    """#14 has two axes, so the four-sided rule must not be applied to it."""
    assert _problems(_record(gap=gap)) == []


@pytest.mark.parametrize("gap", [[1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0]])
def test_a_four_sided_gap_is_refused(gap) -> None:
    assert "1 or 2 px numbers" in _problems(_record(gap=gap))[0]


def test_the_number_list_rule_matches_its_documented_shapes() -> None:
    assert _is_number_list(8, (1, 2, 4)) is True
    assert _is_number_list([8.0, 16.0], (1, 2, 4)) is True
    assert _is_number_list([8.0, 16.0, 8.0], (1, 2, 4)) is False
    # `bool` is an `int` in Python, and `True` as a padding is a typo, not a measurement.
    assert _is_number_list(True, (1, 2, 4)) is False
    assert _is_number_list(float("nan"), (1, 2, 4)) is False


@pytest.mark.parametrize(
    "paint",
    ["#18181B", "#abc", "rgb(24, 24, 27)", "rgba(24, 24, 27, 0.5)", "oklab(0.2 0.0 0.0)", "oklch(0.2 0.0 0.0)"],
)
def test_a_flat_colour_is_a_paint(paint: str) -> None:
    assert _problems(_record(bg=paint)) == []


def test_a_gradient_definition_is_a_paint() -> None:
    """§1 #11: a gradient is a paint, not a colour — #6.1's hole was scoring one as the other."""
    gradient = "linear-gradient(90deg, rgb(233, 240, 28) 0%, rgb(24, 24, 27) 100%)"

    assert _problems(_record(bg=gradient)) == []


def test_an_omitted_property_leaves_no_trace_in_the_contract() -> None:
    """Absence is a *finding* about coverage, not a defect in the bag — §2.6 already
    accounts for it, and refusing the run here would make an incomplete map unusable."""
    assert _problems({"coord_frame": "viewport"}) == []


def test_a_selector_in_the_bag_but_not_the_map_is_checked_and_not_rejected() -> None:
    """An extra measurement is surplus evidence. It is still checked for shape, because a
    malformed record is a sign the extractor was replaced rather than that the map is thin."""
    problems = validate_dom_facts({"#hero": _record(), "#extra": _record(line_height=24)}, ["#hero"])

    assert len(problems) == 1
    assert problems[0].startswith("#extra:")


def test_every_problem_names_its_selector() -> None:
    """A usage error is read once, by whoever has to fix the extraction."""
    problems = validate_dom_facts({"#a": None, "#b": _record(opacity=2)}, ["#a", "#b"])

    assert [p.split(":")[0] for p in problems] == ["#a", "#b"]


# --- Group 3: the contract and the engine must not drift apart ---------------


def test_every_category_property_is_covered_by_the_contract() -> None:
    """A category added without a matching shape rule would skip validation silently —
    the module's whole purpose is to not have silent holes."""
    uncovered = {spec.prop for spec in CATEGORIES} - CHECKED_PROPERTIES

    assert uncovered == set()


def test_the_contract_invents_no_property_the_engine_never_reads() -> None:
    """Two properties are validated without being a scored category, and each earns it.

    `coord_frame` is a precondition rather than a measurement (§2.3): the comparator reads
    it to decide whether `position` may be compared at all, so a wrong one does not produce
    a deviation, it produces a meaningless one. `kind` decides whether typography applies to
    the element. Pinned as an exact set, so a third one cannot appear unnoticed and look like
    a comparison — `line_count` was the third until §1 #18 gave it a category of its own.
    """
    assert CHECKED_PROPERTIES - {spec.prop for spec in CATEGORIES} == {
        "coord_frame",
        "kind",
    }


def test_the_shadow_axes_match_the_category_the_gate_compares() -> None:
    shadow = next(spec for spec in CATEGORIES if spec.key == "shadow")

    assert tuple(shadow.axes) == SHADOW_AXES


# --- Reporting ---------------------------------------------------------------


def test_the_summary_is_one_line_and_counts_what_it_hides() -> None:
    problems = [f"#e{i}: broken" for i in range(9)]

    assert summarise_problems(problems).count("#e") == 6
    assert "… and 3 more" in summarise_problems(problems)
    assert summarise_problems([]) == ""


def test_the_fact_bag_summary_records_the_declared_surface() -> None:
    """`unverified_categories` shows the consequence of a thin extraction, never the cause."""
    summary = fact_bag_summary({"#a": _record(bg="#fff", opacity=None), "#b": _record(line_height=1.5)})

    assert summary["elements"] == 2
    assert summary["properties_collected"] == ["bg", "coord_frame", "line_height"]


# --- The boundary, end to end ------------------------------------------------


def _write(path: Path, payload) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(CHE_CLI_CMD + list(args), capture_output=True, text=True, check=False)


def test_cli_refuses_an_unusable_bag_as_a_usage_error(tmp_path: Path) -> None:
    """Refused, not scored — and refused *before* the comparator, so a run that was never
    measurable does not produce a report someone could mistake for a verdict."""
    design_map = _write(tmp_path / "map.json", {"hero": {"design_node": "n1", "selector": "#hero"}})
    dom = _write(tmp_path / "dom.json", {"#hero": _record(line_height=24)})

    proc = _run_cli(
        "pixel",
        "check",
        "--map",
        design_map,
        "--dom",
        dom,
        "--design",
        design_map,
        "--out",
        str(tmp_path / "report.json"),
    )

    assert proc.returncode == 2
    assert "not usable (1 problem(s))" in proc.stderr
    assert "normalised multiplier" in proc.stderr
    assert "dom-facts-extractor.js" in proc.stderr
    assert not (tmp_path / "report.json").exists()


def test_cli_refuses_a_bag_missing_a_mapped_selector(tmp_path: Path) -> None:
    design_map = _write(
        tmp_path / "map.json",
        {"hero": {"design_node": "n1", "selector": "#hero"}, "cta": {"design_node": "n2", "selector": "#cta"}},
    )
    dom = _write(tmp_path / "dom.json", {"#hero": _record()})

    proc = _run_cli("pixel", "check", "--map", design_map, "--dom", dom, "--design", design_map)

    assert proc.returncode == 2
    assert "#cta" in proc.stderr
    assert "missing_from_dom" in proc.stderr
