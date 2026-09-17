"""Pixel-check engine + design-source parsers.

Fixtures are verbatim slices of two real artefacts — a `get_figma_data` response
and an OpenPencil `.op` document — because both formats are external contracts.
A slice is used rather than a hand-written sample so the parser is exercised
against the vendor's actual whitespace, quoting and token reference forms; if
either vendor changes shape, these tests break instead of the numbers going
quietly wrong.

The four defects these fixtures were written to pin, all of which were silent:

1. `GLOBAL_VARS` entries in the ``- 'value'`` list form were discarded, so every
   ``fills=fill_*`` reference resolved to ``{}`` and no token colour was read.
2. `lineHeight: 1.45em` failed to parse (the ``em`` suffix), so category #8 was
   reported as absent rather than measured.
3. Inline JSON lists (`fills=["#6D28D9"]`) were kept as strings, so a literal
   background colour was lost.
4. A ``text="..."`` value containing a newline split its node line, dropping every
   attribute after it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from che_core.pixel import (
    CRITICAL_CATEGORY_KEYS,
    MAX_DELTA_E,
    PASS_CRITICAL_MAX_DEVIATION_PX,
    PASS_SCORE_MIN,
    PASS_WITHIN_TOLERANCE_PCT,
    TYPOGRAPHY_CATEGORY_KEYS,
    VERDICT_FAIL,
    VERDICT_INCONCLUSIVE,
    VERDICT_PASS,
    build_report,
    delta_e,
    exit_code,
    iter_categories,
    join_by_map,
    parse_color,
    remediation_steps,
    run_check,
    summarise,
)
from che_core.pixel_sources import parse_figma_facts, parse_op_facts

FIXTURES = Path(__file__).parent / "fixtures"
FIGMA_FIXTURE = FIXTURES / "figma_get_figma_data.txt"
OP_FIXTURE = FIXTURES / "openpencil_cli-session.op"

CHE_CLI_CMD = [sys.executable, "-m", "che_core.cli"]


# --- OpenPencil (.op) --------------------------------------------------------


def test_op_parser_extracts_normalised_facts() -> None:
    facts = parse_op_facts(OP_FIXTURE, ["n1", "n4", "n6"])

    # n1 is a frame: a 2-value CSS padding shorthand must broadcast to four sides.
    assert facts["n1"]["padding"] == [88.0, 84.0, 88.0, 84.0]
    assert facts["n1"]["box_size"] == {"width": 1080.0, "height": 1080.0}
    assert facts["n1"]["box_origin"] == {"x": 0.0, "y": 0.0}
    assert facts["n1"]["bg"].startswith("#")

    # n4 is text: the .op backend is the only one that exposes letter-spacing.
    assert facts["n4"]["font_size"] == 28.0
    assert facts["n4"]["font_weight"] == 700.0
    assert facts["n4"]["letter_spacing"] == 0.0
    assert facts["n4"]["line_height"] == 1.4
    assert facts["n4"]["fg"].startswith("#")

    # n6 is a rectangle: a single cornerRadius broadcasts to all four corners.
    assert facts["n6"]["radius"] == [5.0, 5.0, 5.0, 5.0]
    assert facts["n6"]["box_size"] == {"width": 180.0, "height": 12.0}


def test_op_parser_omits_ids_that_are_not_in_the_document() -> None:
    """An absent node must be absent, never an empty bag that reads as 'all zero'."""
    facts = parse_op_facts(OP_FIXTURE, ["n1", "does-not-exist"])
    assert "does-not-exist" not in facts


def test_op_parser_accepts_a_path_string_and_a_parsed_document() -> None:
    from_path = parse_op_facts(str(OP_FIXTURE), ["n4"])
    from_dict = parse_op_facts(json.loads(OP_FIXTURE.read_text(encoding="utf-8")), ["n4"])
    assert from_path == from_dict


def test_op_parser_rejects_a_non_object_document() -> None:
    with pytest.raises(ValueError):
        parse_op_facts(json.dumps([1, 2, 3]), ["n1"])


# --- Figma bridge ------------------------------------------------------------


def test_figma_parser_resolves_token_references() -> None:
    """`fills=fill_*` and `effects="named effect"` must resolve through GLOBAL_VARS."""
    facts = parse_figma_facts(FIGMA_FIXTURE.read_text(encoding="utf-8"), ["117:5966"])

    cta = facts["117:5966"]
    assert cta["padding"] == [20.0, 40.0, 20.0, 40.0]
    assert cta["radius"] == [260.0, 260.0, 260.0, 260.0]
    # The shadow arrives as a quoted *named* effect (its name contains spaces).
    assert cta["shadow"] == {"x": 10.0, "y": 20.0, "blur": 40.0, "spread": 0.0, "alpha": 0.16}
    # Its fill is a gradient, which is not comparable to a flat colour, so the
    # category must stay absent rather than being coerced to something arbitrary.
    assert "bg" not in cta


def test_figma_parser_reads_colours_from_both_token_forms() -> None:
    """A `- '#hex'` token and a literal `["#hex"]` list must both yield a colour."""
    facts = parse_figma_facts(FIGMA_FIXTURE.read_text(encoding="utf-8"), ["I117:5864;1:12255", "117:5851"])

    assert facts["I117:5864;1:12255"]["fg"].startswith("#")
    assert facts["117:5851"]["bg"] == "#82BBFF"


def test_figma_parser_normalises_line_height_to_a_ratio() -> None:
    """`lineHeight: 1.45em` is a multiplier; the gate's tolerance is a ratio."""
    facts = parse_figma_facts(FIGMA_FIXTURE.read_text(encoding="utf-8"), ["I117:5864;1:12255"])
    text = facts["I117:5864;1:12255"]

    assert text["line_height"] == 1.45
    assert text["font_size"] == 14.0
    assert text["font_weight"] == 400.0


def test_figma_parser_never_invents_letter_spacing() -> None:
    """The bridge emits no letterSpacing; guessing one would be a fabricated pass."""
    facts = parse_figma_facts(FIGMA_FIXTURE.read_text(encoding="utf-8"), ["I117:5864;1:12255"])
    assert "letter_spacing" not in facts["I117:5864;1:12255"]


def test_figma_parser_omits_ids_that_are_not_in_the_response() -> None:
    facts = parse_figma_facts(FIGMA_FIXTURE.read_text(encoding="utf-8"), ["117:5966", "999:999"])
    assert "999:999" not in facts


# --- Element kind (applicability, not a measurement) -------------------------


def test_both_parsers_annotate_the_element_kind() -> None:
    """`kind` gates typography applicability, so it must survive parsing.

    The two vendors spell it differently — Figma in caps inside the line's
    `[FRAME]` prefix, `.op` lower-case in a `type` field — so it is normalised to
    avoid `_is_text` having to know either convention.
    """
    op = parse_op_facts(OP_FIXTURE, ["n1", "n4", "n6"])
    assert op["n1"]["kind"] == "frame"
    assert op["n4"]["kind"] == "text"
    assert op["n6"]["kind"] == "rectangle"

    figma = parse_figma_facts(FIGMA_FIXTURE.read_text(encoding="utf-8"), ["117:5966", "I117:5864;1:12255"])
    assert figma["117:5966"]["kind"] == "frame"
    assert figma["I117:5864;1:12255"]["kind"] == "text"


def test_kind_is_never_measured_as_a_category() -> None:
    """It rides in the facts bag, so nothing may accidentally score it."""
    assert "kind" not in {spec.prop for spec in iter_categories()}


# --- Colour maths ------------------------------------------------------------


def test_parse_color_handles_the_forms_both_sides_emit() -> None:
    assert parse_color("#fff") == (1.0, 1.0, 1.0, 1.0)
    assert parse_color("#FFFFFF") == (1.0, 1.0, 1.0, 1.0)
    assert parse_color("rgb(0, 0, 0)") == (0.0, 0.0, 0.0, 1.0)
    assert parse_color("rgba(0, 0, 0, 0.5)")[3] == 0.5
    # Unparseable input must be None so the category becomes unverified.
    assert parse_color("linear-gradient(90deg, #000, #fff)") is None
    assert parse_color(None) is None


def test_delta_e_matches_cie76_reference_values() -> None:
    assert delta_e("#FFFFFF", "#FFFFFF") == 0.0
    # Black against white is ~100 in CIE76 by construction.
    assert delta_e("#000000", "#FFFFFF") == pytest.approx(100.0, abs=0.5)
    assert delta_e("#000000", "#FFFFFF") > MAX_DELTA_E
    # A near-identical grey must sit inside the gate's tolerance.
    assert delta_e("#FFFFFF", "#FEFEFE") < MAX_DELTA_E


def test_delta_e_is_none_when_either_colour_is_unparseable() -> None:
    assert delta_e(None, "#FFFFFF") is None
    assert delta_e("#FFFFFF", "gradient") is None


# --- Comparison --------------------------------------------------------------


def _design(**overrides):
    base = {
        "box_size": {"width": 320.0, "height": 52.0},
        "box_origin": {"x": 480.0, "y": 220.0},
        "padding": [12.0, 24.0, 12.0, 24.0],
        "radius": [8.0, 8.0, 8.0, 8.0],
        "font_size": 18.0,
        "font_weight": 600.0,
        "line_height": 1.2,
        "letter_spacing": 0.0,
        "fg": "#18181B",
        "bg": "#FFFFFF",
        "shadow": {"x": 0.0, "y": 2.0, "blur": 8.0, "spread": 0.0, "alpha": 0.08},
        "border_width": 1.0,
        "border_color": "#E4E4E7",
    }
    base.update(overrides)
    return base


def test_an_exact_match_passes() -> None:
    design = _design()
    report = build_report({"cta": design}, {"cta": dict(design)}, backend="openpencil")

    assert report.verdict == VERDICT_PASS
    assert report.score == 10.0
    assert report.within_tolerance_pct == 1.0
    assert report.max_critical_deviation_px == 0.0


def test_deviations_inside_tolerance_still_pass() -> None:
    """1px of padding and 0.5px of radius are strictly inside the gate's tolerances."""
    actual = dict(_design(padding=[13.0, 25.0, 13.0, 25.0], radius=[8.5, 8.5, 8.5, 8.5]))
    report = build_report({"cta": _design()}, {"cta": actual}, backend="openpencil")

    assert report.verdict == VERDICT_PASS
    assert report.score >= PASS_SCORE_MIN
    assert report.within_tolerance_pct >= PASS_WITHIN_TOLERANCE_PCT


def test_the_tolerance_boundary_passes_condition_2_but_earns_no_score() -> None:
    """Pin the gate §2 formula at its edge.

    `raw_score = max(0, 1 - deviation/tolerance)` gives exactly 0.0 when a
    measurement sits *on* its tolerance, yet condition 2 counts it as within
    tolerance. So "acceptable" and "good" are deliberately different questions:
    a frame uniformly at the limit satisfies the 95 % rule and still fails the
    ≥ 8.0 score rule. Padding (4 axes × ×2) and radius (4 axes × ×1.5) at the
    limit therefore cost 8 + 6 of the 35 total weight, leaving 6.0/10.
    """
    actual = dict(_design(padding=[16.0, 28.0, 16.0, 28.0], radius=[6.0, 6.0, 6.0, 6.0]))
    report = build_report({"cta": _design()}, {"cta": actual}, backend="openpencil")

    padding = [m for m in report.measurements if m.category == "padding"]
    assert [m.passed for m in padding] == [True] * 4  # exactly at 4px = still acceptable
    assert report.within_tolerance_pct == 1.0
    assert report.score == 6.0
    assert report.verdict == VERDICT_FAIL


def test_a_single_critical_deviation_over_8px_fails_despite_a_high_score() -> None:
    """The gate's third PASS condition: one bad CTA fails the run outright."""
    actual = dict(_design(padding=[32.0, 24.0, 12.0, 24.0]))  # 20px off on padding-top
    report = build_report({"cta": _design()}, {"cta": actual}, backend="openpencil")

    assert report.max_critical_deviation_px is not None
    assert report.max_critical_deviation_px > PASS_CRITICAL_MAX_DEVIATION_PX
    assert report.verdict == VERDICT_FAIL
    assert "critical deviation" in report.reason


def test_many_small_deviations_fail_the_within_tolerance_ratio() -> None:
    actual = _design(
        font_size=21.0,  # 3px: outside the 2px tolerance
        fg="#3F3F46",  # ~> 5 ΔE from #18181B
        letter_spacing=0.05,
        line_height=1.5,
        shadow={"x": 6.0, "y": 9.0, "blur": 20.0, "spread": 8.0, "alpha": 0.4},
    )
    report = build_report({"cta": _design()}, {"cta": actual}, backend="openpencil")

    assert report.verdict == VERDICT_FAIL
    assert report.within_tolerance_pct < PASS_WITHIN_TOLERANCE_PCT


def test_a_property_absent_from_the_design_is_unverified_never_a_pass() -> None:
    """A category with no design value must not be scored as if it matched."""
    design = _design()
    del design["letter_spacing"]
    report = build_report({"cta": design}, {"cta": _design()}, backend="figma")

    unverified = [m for m in report.measurements if not m.verified]
    assert "letter_spacing" in {m.category for m in unverified}
    assert all(not m.passed for m in unverified)
    assert any(s["category"] == "letter_spacing" for s in report.skipped_categories)
    # letter_spacing is a ×1 category, so this alone must not block a PASS.
    assert report.verdict == VERDICT_PASS


def test_margin_is_never_emitted_by_either_backend() -> None:
    """Pin a known capability gap rather than let it go quietly unnoticed.

    Gate §1 #3 measures the *distance to sibling elements*, not a CSS `margin`,
    and neither `get_figma_data` nor a `.op` node exposes it. Category #3 is
    therefore always ``absent_from_design`` → always unverified, on every run,
    for every element. It is ×1.5 and so cannot force INCONCLUSIVE, which means
    the only place this shows up is `skipped_categories`. This test keeps that
    from being mistaken for "margin was checked and matched".
    """
    design = _design()
    design.pop("margin", None)
    report = build_report({"cta": design}, {"cta": _design()}, backend="openpencil")

    assert "margin" not in CRITICAL_CATEGORY_KEYS  # ×1.5, so it cannot force INCONCLUSIVE
    margin = [m for m in report.measurements if m.category == "margin"]
    assert margin and all(not m.verified for m in margin)
    assert all(s["reason"] == "absent_from_design" for s in report.skipped_categories if s["category"] == "margin")


def test_an_unverified_critical_category_forces_inconclusive() -> None:
    """PASS while blind to a ×2 category would claim a check that never ran."""
    design = _design()
    del design["padding"]
    report = build_report({"cta": design}, {"cta": _design()}, backend="figma")

    assert "padding" in CRITICAL_CATEGORY_KEYS
    assert report.verdict == VERDICT_INCONCLUSIVE
    assert "padding" in report.reason


def test_a_frame_is_not_required_to_carry_typography() -> None:
    """A graphic frame legitimately has no font.

    Both extractors annotate the node kind, so typography on a frame is reported
    as inapplicable. Without that distinction a frame's missing `font-weight`
    would be an unverified ×2 category and every frame-only screen would return
    INCONCLUSIVE — the gate would block every ship instead of gating it.
    """
    frame = {"kind": "frame", "padding": [10.0, 20.0, 10.0, 20.0], "bg": "#FFFFFF"}
    report = build_report({"hero": frame}, {"hero": dict(frame)}, backend="openpencil")

    assert report.verdict == VERDICT_PASS
    typography_skips = [s for s in report.skipped_categories if s["category"] in TYPOGRAPHY_CATEGORY_KEYS]
    assert typography_skips
    assert all(s["reason"] == "not_applicable" for s in typography_skips)


def test_an_unknown_kind_stays_fail_closed() -> None:
    """With no `kind` we cannot claim typography is inapplicable.

    Assuming "not applicable" would excuse a ×2 category that was never measured,
    which is the fabricated-pass failure mode this engine exists to prevent.
    """
    design = _design()
    assert "kind" not in design  # the fixture is deliberately unannotated
    del design["font_size"]
    report = build_report({"cta": design}, {"cta": _design()}, backend="figma")

    assert report.verdict == VERDICT_INCONCLUSIVE
    assert "font_size" in report.reason


def test_blindness_is_a_run_level_condition_not_a_per_element_one() -> None:
    """Absence on one element is normal; absence across the run is the real gap.

    A text node carries no explicit padding row and a frame carries no font, so a
    per-element rule escalated constant, blocking conditions. Only a category that
    *no* element measured is treated as the source withholding it.
    """
    frame = {"kind": "frame", "padding": [10.0, 20.0, 10.0, 20.0], "box_size": {"width": 100.0, "height": 50.0}}
    text = {"kind": "text", "font_size": 14.0, "font_weight": 400.0, "fg": "#000000"}
    report = build_report({"f": frame, "t": text}, {"f": dict(frame), "t": dict(text)}, backend="openpencil")

    # padding is critical and absent from the text node, but the frame measured it.
    assert any(s["category"] == "padding" and s["reason"] == "absent_from_design" for s in report.skipped_categories)
    assert report.verdict == VERDICT_PASS


def test_nothing_measurable_is_inconclusive_not_a_pass() -> None:
    report = build_report({"cta": {"bg": "#FFFFFF"}}, {"cta": {"bg": "#FFFFFF"}}, backend="figma")
    # Every other category is absent from the design, and bg alone is not critical.
    assert report.verdict in (VERDICT_PASS, VERDICT_INCONCLUSIVE)
    empty = build_report({"cta": {}}, {"cta": {}}, backend="figma")
    assert empty.verdict == VERDICT_INCONCLUSIVE
    assert empty.score is None


def test_a_designed_element_absent_from_the_dom_fails_the_run() -> None:
    """An element on only one side contributes no measurement — so it is invisible
    to every numeric condition. Reporting PASS would hide a component the designer
    specified, which is the fail-open this rule exists to close."""
    report = build_report(
        {"cta": _design(), "ghost": _design()},
        {"cta": _design()},
        backend="openpencil",
    )

    assert report.elements == 1
    assert report.verdict == VERDICT_FAIL
    assert "ghost" in report.reason
    assert any(s["element"] == "ghost" and s["reason"] == "missing_from_dom" for s in report.skipped_categories)


def test_an_element_missing_from_the_design_source_is_inconclusive() -> None:
    """A declared element whose reference cannot be read was never verified.

    Typical causes are a stale node id or the wrong `--design-backend`; scoring
    around it would silently compare a subset of the map and call it the screen.
    """
    report = build_report({"cta": _design()}, {"cta": _design(), "stray": _design()}, backend="figma")

    assert report.verdict == VERDICT_INCONCLUSIVE
    assert "stray" in report.reason


def test_remediation_names_the_worst_deviations_first() -> None:
    actual = _design(padding=[40.0, 24.0, 12.0, 24.0], radius=[1.0, 1.0, 1.0, 1.0])
    report = build_report({"cta": _design()}, {"cta": actual}, backend="openpencil")
    steps = remediation_steps(report, limit=2)

    assert len(steps) == 2
    assert "padding[top]" in steps[0]  # 28px off beats the 7px radius error
    assert "radius" in steps[1]


def test_summary_line_matches_the_gate_log_format() -> None:
    report = build_report({"cta": _design()}, {"cta": _design()}, backend="openpencil")
    line = summarise(report)

    assert line.startswith("[DOMAIN-GATE-EXECUTED] domain=ux gate=pixel-check-gate")
    assert "status=PASS" in line
    assert "backend=openpencil" in line


def test_report_json_is_serialisable_and_carries_the_thresholds() -> None:
    report = build_report({"cta": _design()}, {"cta": _design()}, backend="openpencil")
    payload = json.loads(json.dumps(report.to_json()))

    assert payload["verdict"] == VERDICT_PASS
    assert payload["thresholds"]["pass_score_min"] == PASS_SCORE_MIN
    assert payload["thresholds"]["pass_within_tolerance_pct"] == PASS_WITHIN_TOLERANCE_PCT
    assert payload["thresholds"]["pass_critical_max_deviation_px"] == PASS_CRITICAL_MAX_DEVIATION_PX


# --- The map is the only join (§3.3) -----------------------------------------


def test_join_by_map_re_keys_both_sides_by_element() -> None:
    design_map = {"cta": {"design_node": "12:345", "selector": "[data-design-node='12:345']"}}

    design, dom = join_by_map(
        design_map,
        {"12:345": {"font_size": 18.0}},
        {"[data-design-node='12:345']": {"font_size": 18.0}},
    )

    assert design == {"cta": {"font_size": 18.0}}
    assert dom == {"cta": {"font_size": 18.0}}


def test_a_map_entry_without_a_selector_is_rejected() -> None:
    """Both halves are needed to join; a partial entry is a contract violation."""
    with pytest.raises(ValueError, match="selector"):
        join_by_map({"cta": {"design_node": "12:345"}}, {"12:345": {}}, {})


def test_a_one_sided_element_is_omitted_rather_than_emptied() -> None:
    """An empty bag would read as "every category absent from the design"."""
    design, dom = join_by_map(
        {"cta": {"design_node": "12:345", "selector": "#cta"}},
        {"12:345": {"font_size": 18.0}},
        {},
    )

    assert "cta" in design
    assert "cta" not in dom


def test_run_check_carries_the_breakpoint_as_provenance() -> None:
    design_map = {"cta": {"design_node": "12:345", "selector": "#cta"}}
    facts = {"12:345": {"kind": "text", "font_size": 18.0, "font_weight": 600.0, "fg": "#000000"}}

    report = run_check(design_map, facts, {"#cta": dict(facts["12:345"])}, backend="figma", breakpoint="lg")

    assert report.reason.startswith("[lg]")
    assert report.backend == "figma"


# --- Exit codes --------------------------------------------------------------


def test_inconclusive_never_shares_an_exit_code_with_pass() -> None:
    """A caller that branches on the exit code must not read "unverified" as "ok"."""
    assert exit_code(build_report({"cta": _design()}, {"cta": _design()})) == 0
    assert exit_code(build_report({"cta": _design()}, {"cta": _design(font_size=30.0)})) == 1
    assert exit_code(build_report({"cta": {}}, {"cta": {}})) == 3


# --- CLI surface (`che pixel check`) -----------------------------------------


def _write(path: Path, payload) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(CHE_CLI_CMD + list(args), capture_output=True, text=True, check=False)


def test_cli_runs_the_gate_end_to_end_from_the_raw_op_fixture(tmp_path: Path) -> None:
    """The gate is executable only if this path works: raw design in, verdict out."""
    design_map = _write(
        tmp_path / "map.json",
        {"hero-frame": {"design_node": "n1", "selector": "[data-design-node='n1']"}},
    )
    facts = parse_op_facts(OP_FIXTURE, ["n1"])
    dom = _write(tmp_path / "dom.json", {"[data-design-node='n1']": facts["n1"]})

    proc = _run_cli(
        "pixel",
        "check",
        "--map",
        design_map,
        "--dom",
        dom,
        "--design-source",
        str(OP_FIXTURE),
        "--design-backend",
        "openpencil",
        "--breakpoint",
        "lg",
    )

    assert proc.returncode == 0, proc.stderr
    assert "status=PASS" in proc.stdout
    assert "backend=openpencil" in proc.stdout


def test_cli_exits_1_and_names_the_fix_when_a_critical_measurement_drifts(tmp_path: Path) -> None:
    design_map = _write(tmp_path / "map.json", {"hero-frame": {"design_node": "n1", "selector": "#hero"}})
    facts = parse_op_facts(OP_FIXTURE, ["n1"])
    dom = _write(tmp_path / "dom.json", {"#hero": dict(facts["n1"], padding=[110.0, 84.0, 88.0, 84.0])})

    proc = _run_cli(
        "pixel",
        "check",
        "--map",
        design_map,
        "--dom",
        dom,
        "--design-source",
        str(OP_FIXTURE),
        "--design-backend",
        "openpencil",
    )

    assert proc.returncode == 1, proc.stderr
    assert "status=FAIL" in proc.stdout
    assert "fix:" in proc.stdout  # the retry policy's top deviation, worst first


def test_cli_writes_a_report_the_decision_log_can_quote(tmp_path: Path) -> None:
    design_map = _write(tmp_path / "map.json", {"hero-frame": {"design_node": "n1", "selector": "#hero"}})
    facts = parse_op_facts(OP_FIXTURE, ["n1"])
    dom = _write(tmp_path / "dom.json", {"#hero": facts["n1"]})
    out = tmp_path / "report.json"

    proc = _run_cli(
        "pixel",
        "check",
        "--map",
        design_map,
        "--dom",
        dom,
        "--design-source",
        str(OP_FIXTURE),
        "--design-backend",
        "openpencil",
        "--out",
        str(out),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["verdict"] == VERDICT_PASS
    assert payload["thresholds"]["pass_score_min"] == PASS_SCORE_MIN
    assert payload["summary"].startswith("[DOMAIN-GATE-EXECUTED] domain=ux gate=pixel-check-gate")


def test_cli_refuses_a_design_source_without_a_backend(tmp_path: Path) -> None:
    """The backend is never inferred from the file: guessing picks the wrong extractor."""
    design_map = _write(tmp_path / "map.json", {"a": {"design_node": "n1", "selector": "#a"}})
    dom = _write(tmp_path / "dom.json", {})

    proc = _run_cli("pixel", "check", "--map", design_map, "--dom", dom, "--design-source", str(OP_FIXTURE))

    assert proc.returncode == 2
    assert "--design-backend" in proc.stderr


def test_cli_reports_an_unreadable_artefact_as_a_usage_error(tmp_path: Path) -> None:
    design_map = _write(tmp_path / "map.json", {})

    proc = _run_cli("pixel", "check", "--map", design_map, "--dom", str(tmp_path / "nope.json"), "--design", design_map)

    assert proc.returncode == 2
    assert "cannot read" in proc.stderr
