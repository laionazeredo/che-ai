"""Pixel-check engine + design-source parsers.

Fixtures are verbatim slices of two real artefacts — a `get_figma_data` response
and an OpenPencil `.op` document — because both formats are external contracts.
A slice is used rather than a hand-written sample so the parser is exercised
against the vendor's actual whitespace, quoting and token reference forms; if
either vendor changes shape, these tests break instead of the numbers going
quietly wrong.

The seven defects these fixtures were written to pin, all of which were silent:

1. `GLOBAL_VARS` entries in the ``- 'value'`` list form were discarded, so every
   ``fills=fill_*`` reference resolved to ``{}`` and no token colour was read.
2. `lineHeight: 1.45em` failed to parse (the ``em`` suffix), so category #8 was
   reported as absent rather than measured.
3. Inline JSON lists (`fills=["#6D28D9"]`) were kept as strings, so a literal
   background colour was lost.
4. A ``text="..."`` value containing a newline split its node line, dropping every
   attribute after it.
5. Auto-layout `gap` was not a category at all, so the mechanism modern frames use
   to space their children was invisible while `margin` — its legacy form — was
   never emitted by any backend.
6. An omitted zero `padding` on an auto-layout container was read as the source
   withholding it. That made a ×2 critical category unverifiable on *every*
   auto-layout screen, so a page whose every other property was measurable still
   returned INCONCLUSIVE and could never reach a verdict.
7. `oklab(…)` was unparseable. Tailwind v4 compiles an opacity modifier such as
   `text-white/90` to `color-mix(in oklab, …)`, and Chrome reports the computed
   value in that space — so the colour category was dropped rather than compared.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from che_core.pixel import (
    CATEGORIES,
    CRITICAL_CATEGORY_KEYS,
    MAX_DELTA_E,
    PASS_CRITICAL_MAX_DEVIATION_PX,
    PASS_SCORE_MIN,
    PASS_WITHIN_TOLERANCE_PCT,
    TYPOGRAPHY_CATEGORY_KEYS,
    UNREACHABLE_CATEGORY_KEYS,
    VERDICT_FAIL,
    VERDICT_INCONCLUSIVE,
    VERDICT_PASS,
    build_report,
    delta_e,
    design_facts_record,
    exit_code,
    iter_categories,
    join_by_map,
    parse_color,
    parse_gradient,
    remediation_steps,
    resolve_design_source,
    run_check,
    summarise,
)
from che_core.pixel_sources import (
    BACKENDS_WITH_EXTRACTOR,
    BACKENDS_WITHOUT_EXTRACTOR,
    DECLARED_BACKENDS,
    parse_figma_facts,
    parse_op_facts,
)

FIXTURES = Path(__file__).parent / "fixtures"
FIGMA_FIXTURE = FIXTURES / "figma_get_figma_data.txt"
FIGMA_AUTOLAYOUT_FIXTURE = FIXTURES / "figma_autolayout_frames.txt"
OP_FIXTURE = FIXTURES / "openpencil_cli-session.op"

CHE_CLI_CMD = [sys.executable, "-m", "che_core.cli"]


# --- OpenPencil (.op) --------------------------------------------------------


def test_op_parser_extracts_normalised_facts() -> None:
    facts = parse_op_facts(OP_FIXTURE, ["n1", "n4", "n6"])

    # n1 is a frame: a 2-value CSS padding shorthand must broadcast to four sides.
    assert facts["n1"]["padding"] == [88.0, 84.0, 88.0, 84.0]
    assert facts["n1"]["box_size"] == {"width": 1080.0, "height": 1080.0}
    # `bg` is always a stack, even when it holds one paint: one shape for one property, so the
    # comparator never has to guess whether a value is a layer list or a single layer.
    assert facts["n1"]["bg"] == ["#FFF7ED"]

    # n4 is text: the .op backend is the only one that exposes letter-spacing.
    assert facts["n4"]["font_size"] == 28.0
    assert facts["n4"]["font_weight"] == 700.0
    assert facts["n4"]["letter_spacing"] == 0.0
    assert facts["n4"]["line_height"] == 1.4
    assert facts["n4"]["fg"].startswith("#")

    # n6 is a rectangle: a single cornerRadius broadcasts to all four corners.
    assert facts["n6"]["radius"] == [5.0, 5.0, 5.0, 5.0]
    assert facts["n6"]["box_size"] == {"width": 180.0, "height": 12.0}


def test_op_parser_never_emits_a_position() -> None:
    """An `.op` document is auto-layout: there are no coordinates to compare.

    Only the root carries an x/y in the whole document, and it sits at its own
    origin. Emitting that 0,0 as `box_origin` produced a guaranteed false FAIL
    against any real `getBoundingClientRect()`, so the backend declares the frame
    unobtainable instead of approximating one.
    """
    facts = parse_op_facts(OP_FIXTURE, ["n1", "n4"])

    assert "box_origin" not in facts["n1"]
    assert all(node["coord_frame"] == "none" for node in facts.values())


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
    # Its fill is a gradient. That is a paint, not a colour, so it is carried through
    # as its CSS definition and compared structurally by the comparator — recording it
    # as "absent" is exactly what let a gradient design pass against a flat
    # implementation (§6.1). This assertion used to pin the old, wrong behaviour.
    assert cta["bg"] == ["linear-gradient(239deg, rgba(98, 70, 229, 1) 0%, rgba(155, 98, 192, 1) 96%)"]


def test_figma_parser_reads_colours_from_both_token_forms() -> None:
    """A `- '#hex'` token and a literal `["#hex"]` list must both yield a colour."""
    facts = parse_figma_facts(FIGMA_FIXTURE.read_text(encoding="utf-8"), ["I117:5864;1:12255", "117:5851"])

    assert facts["I117:5864;1:12255"]["fg"].startswith("#")
    assert facts["117:5851"]["bg"] == ["#82BBFF"]


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


# --- Auto-layout spacing (#14 `gap`, and padding's implicit zero) -------------


def test_figma_parser_reads_an_auto_layout_gap() -> None:
    """`gap` is how a modern frame spaces its children.

    Gate §1 #3 asks for the space *between* elements, but a frame expresses it as
    auto-layout `gap` far more often than as a `margin` — and no backend ever
    emitted a margin. Without #14 the design's actual spacing mechanism was
    invisible to the gate.
    """
    facts = parse_figma_facts(FIGMA_AUTOLAYOUT_FIXTURE.read_text(encoding="utf-8"), ["I117:7236;99:1143"])

    # A uniform gap is written as one value and deliberately left un-broadcast:
    # the comparator's coercion is the single place that decides how a short list
    # fills its axes.
    assert facts["I117:7236;99:1143"]["gap"] == [20.0]


def test_figma_parser_reads_a_paired_gap_as_row_then_column() -> None:
    facts = parse_figma_facts(FIGMA_AUTOLAYOUT_FIXTURE.read_text(encoding="utf-8"), ["I117:7236;99:1139"])

    assert facts["I117:7236;99:1139"]["gap"] == [30.0, 0.0]


def test_op_parser_reads_an_auto_layout_gap() -> None:
    facts = parse_op_facts(OP_FIXTURE, ["n1", "n2"])

    assert facts["n1"]["gap"] == [0.0]  # a zero gap is a spacing decision, not an absence
    assert facts["n2"]["gap"] == [22.0]


def test_a_container_that_omits_its_zero_padding_is_read_as_zero() -> None:
    """Both vendors leave the property out when it is zero, and zero is still a value.

    Padding exists only on an auto-layout container. Reading its omission as "the
    source withheld padding" made a ×2 critical category unverifiable on every
    auto-layout screen, so a page whose every other property was measurable still
    returned INCONCLUSIVE and could never reach a verdict.
    """
    figma = parse_figma_facts(FIGMA_AUTOLAYOUT_FIXTURE.read_text(encoding="utf-8"), ["I117:7236;99:1142"])
    op = parse_op_facts(OP_FIXTURE, ["n2"])

    assert figma["I117:7236;99:1142"]["padding"] == [0.0, 0.0, 0.0, 0.0]
    assert op["n2"]["padding"] == [0.0, 0.0, 0.0, 0.0]


def test_padding_is_not_invented_for_a_node_that_cannot_have_it() -> None:
    """Zero here is a reading of the design; for a text node it would be a fabrication.

    A text node and a rectangle have no padding concept at all, so nothing is
    emitted and the category stays unverified rather than scoring against a value
    the designer never set.
    """
    figma = parse_figma_facts(FIGMA_AUTOLAYOUT_FIXTURE.read_text(encoding="utf-8"), ["I117:7236;1:11886"])
    op = parse_op_facts(OP_FIXTURE, ["n4", "n6"])

    assert "padding" not in figma["I117:7236;1:11886"]
    assert "padding" not in op["n4"]
    assert "padding" not in op["n6"]


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


# --- Text reflow: a line count is stated only where wrapping cannot happen ----
#
# §6.1 listed this as "half-collected, still not scored". The half that was missing is the
# design side, and the only honest way to supply it is to say when the answer is knowable:
# if the text box grows with its content, the rendered lines are the text's own breaks. A
# fixed or filled box wraps at a width the source never reports, and the property is omitted
# rather than invented — an absent value is unverified, which is not a pass.


def test_the_op_parser_counts_lines_for_text_that_hugs_its_content() -> None:
    hugged = {"type": "text", "id": "n1", "textGrowth": "auto", "content": "one line"}
    wrapped = {"type": "text", "id": "n1", "textGrowth": "auto", "content": "line one\nline two"}

    assert _op_facts_for(hugged)["line_count"] == 1
    assert _op_facts_for(wrapped)["line_count"] == 2


def test_the_op_parser_stays_silent_where_wrapping_is_possible() -> None:
    """`fixed-width` wraps at a width the document never states, so there is no count to give."""
    fixed = {"type": "text", "id": "n1", "textGrowth": "fixed-width", "content": "Pão quente"}
    unstated = {"type": "text", "id": "n1", "content": "Pão quente"}
    contentless = {"type": "text", "id": "n1", "textGrowth": "auto"}

    assert "line_count" not in _op_facts_for(fixed)
    assert "line_count" not in _op_facts_for(unstated)
    # Without the text even the explicit breaks are unknown, so a hug is not enough on its own.
    assert "line_count" not in _op_facts_for(contentless)


def test_the_figma_parser_reads_the_hug_sizing_when_the_response_states_it() -> None:
    hug = '[TEXT] "label" #1:1 layout={"mode":"none","sizing":{"horizontal":"hug"}} text="one line"'

    assert _figma_facts_for(hug)["line_count"] == 1


def test_the_figma_parser_stays_silent_on_a_filled_or_silent_box() -> None:
    filled = '[TEXT] "label" #1:1 layout={"mode":"none","sizing":{"horizontal":"fill"}} text="a long run of words"'
    silent = '[TEXT] "label" #1:1 layout={"mode":"none","sizing":{}} text="a long run of words"'

    assert "line_count" not in _figma_facts_for(filled)
    assert "line_count" not in _figma_facts_for(silent)


def test_a_line_that_wrapped_in_the_implementation_is_a_deviation() -> None:
    """The defect this category exists for: the design hugs, the browser wraps."""
    design = _design(line_count=1, kind="text")
    actual = _design(line_count=2, kind="text")
    report = build_report({"cta": design}, {"cta": actual}, backend="figma")

    lines = [m for m in report.measurements if m.category == "line_count"]
    assert len(lines) == 1
    assert lines[0].verified
    assert not lines[0].passed
    assert lines[0].deviation == 1.0


def test_a_frame_has_no_lines_to_wrap() -> None:
    """Absent on a non-text element is `not_applicable`, not a gap — a frame has no lines."""
    design = _design(kind="frame")
    actual = _design(kind="frame")
    report = build_report({"hero": design}, {"hero": actual}, backend="figma")

    skipped = [s for s in report.skipped_categories if s["category"] == "line_count"]
    assert skipped and all(s["reason"] == "not_applicable" for s in skipped)


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


def test_parse_color_reads_the_oklab_form_a_browser_reports() -> None:
    """Tailwind v4 compiles `text-white/90` to `color-mix(in oklab, …)`.

    Chrome reports the computed value in that space. Returning `None` made the
    category silently unverified — a hole rather than a failure, since a dropped
    category neither passes nor fails, it just stops being checked.
    """
    reported = "oklab(0.999994 0.0000455678 0.0000200868 / 0.9)"
    rgba = parse_color(reported)

    assert rgba is not None
    assert rgba[3] == 0.9
    assert rgba[:3] == pytest.approx((1.0, 1.0, 1.0), abs=1e-3)
    # And it must land inside ΔE tolerance of the hex the design states for white.
    assert delta_e("#FFFFFF", reported) < MAX_DELTA_E


def test_parse_color_reads_oklch() -> None:
    assert parse_color("oklch(0.6280 0.2577 29.23)") == pytest.approx((1.0, 0.0, 0.0, 1.0), abs=1e-3)


def test_parse_color_handles_percentages_and_refuses_a_truncated_list() -> None:
    assert parse_color("oklab(100% 0 0)") == pytest.approx((1.0, 1.0, 1.0, 1.0), abs=1e-3)
    # A list without exactly three components is not a colour; defaulting the
    # missing one would be a fabricated value rather than a measurement.
    assert parse_color("oklab(1 0)") is None
    assert parse_color("oklab(1 0 nope)") is None
    assert parse_color("oklch(0.7 0.1 30 40)") is None


def test_an_oklab_colour_is_compared_rather_than_dropped() -> None:
    design = _design(fg="#FFFFFF")
    actual = _design(fg="oklab(0.999994 0.0000455678 0.0000200868 / 0.9)")
    report = build_report({"cta": design}, {"cta": actual}, backend="figma")

    fg = [m for m in report.measurements if m.category == "fg_color"]
    assert fg and all(m.verified for m in fg)
    assert (fg[0].deviation or 0.0) < MAX_DELTA_E


# --- Paints: a stack is compared layer by layer (§6.1) ------------------------
#
# `bg` used to be the first *resolvable* fill. On a two-fill node that is the bottom layer
# alone, so an implementation that dropped the top one — a tint over a base, a gradient over a
# colour — matched the base and passed. The tests below pin the three ways that is now closed:
# the stack is read whole, a stack nobody can order is omitted rather than guessed, and a
# missing layer is reported where it went missing.


def _figma_facts_for(line: str, node_id: str = "1:1") -> dict:
    """One synthetic bridge response in the rendered form, through the real parser.

    The `NODES:` header is load-bearing: the parser splits the response into sections before it
    reads a node line, and a bare line parses to nothing — silently, which is why the header is
    spelled out here rather than left implicit.
    """
    return parse_figma_facts(f"NODES:\n{line}\n", [node_id])[node_id]


def _op_facts_for(node: dict, node_id: str = "n1") -> dict:
    """One synthetic `.op` node, through the real parser."""
    return parse_op_facts(json.dumps({"children": [node]}), [node_id]).get(node_id, {})


def _extractor_source() -> str:
    """The implementation-side extractor, for the two orderings only it can show."""
    return (
        Path(__file__).resolve().parent.parent / "domains" / "ux" / "gates" / "assets" / "dom-facts-extractor.js"
    ).read_text(encoding="utf-8")


def test_the_figma_parser_keeps_the_whole_fill_stack_in_source_order() -> None:
    """Figma states `fills` bottom-to-top, so the array is carried through as read."""
    line = '[FRAME] "stack" #1:1 layout={"mode":"none"} fills=["#111111", "#222222"]'

    assert _figma_facts_for(line)["bg"] == ["#111111", "#222222"]


def test_a_fill_the_extractor_cannot_read_omits_the_whole_stack() -> None:
    """Skipping an unreadable layer would shift every pair after it.

    An image fill is not a paint this comparator can compare, so the honest answer is "this
    stack is not measurable" — not the *other* layers compared at the wrong indices, which
    would report a deviation between two paints that were never lined up. The coverage is
    genuinely lost here, and that is the smaller loss: the value it replaces claimed to be
    the background while describing only its bottom layer.
    """
    line = '[FRAME] "stack" #1:1 layout={"mode":"none"} fills=["#111111", {"type": "IMAGE", "imageHash": "abc"}]'

    assert "bg" not in _figma_facts_for(line)


def test_the_op_parser_refuses_a_stack_whose_order_it_cannot_establish() -> None:
    """`.op` documents no direction for `fill`, so a stack is omitted rather than reversed.

    Every node in the sampled documents holds one paint, and one paint has no order — so
    refusing the stack costs the readable cases nothing while keeping the unreadable one
    from being guessed at.
    """
    stacked = {
        "type": "frame",
        "id": "n1",
        "fill": [{"type": "solid", "color": "#111111"}, {"type": "solid", "color": "#222222"}],
    }
    single = {"type": "frame", "id": "n1", "fill": [{"type": "solid", "color": "#111111"}]}

    assert "bg" not in _op_facts_for(stacked)
    assert _op_facts_for(single)["bg"] == ["#111111"]


def test_a_dropped_layer_is_a_mismatch_reported_on_the_missing_layer() -> None:
    """The finding is the absent layer, and the report has to say which one it was."""
    design = _design(bg=["#FFFFFF", "#000000"])
    actual = _design(bg=["#FFFFFF"])
    report = build_report({"cta": design}, {"cta": actual}, backend="figma")

    layers = [m for m in report.measurements if m.category == "bg_color"]
    assert [m.axis for m in layers] == ["layer[0]", "layer[1]"]
    assert layers[0].passed
    assert not layers[1].passed
    assert layers[1].design == "#000000"
    assert layers[1].actual is None


def test_a_wrong_layer_is_a_mismatch_naming_that_layer() -> None:
    """Layer by layer, so the report points at the paint that is wrong, not at the whole box."""
    design = _design(bg=["#FFFFFF", "#000000"])
    actual = _design(bg=["#FFFFFF", "#FF0000"])
    report = build_report({"cta": design}, {"cta": actual}, backend="figma")

    layers = [m for m in report.measurements if m.category == "bg_color"]
    assert layers[0].passed
    assert not layers[1].passed
    assert (layers[1].deviation or 0.0) > MAX_DELTA_E


def test_a_single_paint_still_compares_as_a_bare_string() -> None:
    """One shape for `bg`, but not a stricter input contract than the engine needs."""
    report = build_report({"cta": _design(bg="#FFFFFF")}, {"cta": _design(bg=["#FFFFFF"])}, backend="figma")

    layers = [m for m in report.measurements if m.category == "bg_color"]
    assert len(layers) == 1
    assert layers[0].verified and layers[0].passed


def test_the_dom_extractor_re_orders_css_layers_to_the_design_direction() -> None:
    """CSS names `background-image` top-first and paints `background-color` underneath all of
    them; the design side states `fills` bottom-to-top.

    The reversal *is* the comparison, so it is pinned by reading the extractor: dropping it
    would pair the top paint of one side with the bottom paint of the other and report a
    deviation between two layers that were never meant to match.
    """
    source = _extractor_source()

    assert ".reverse()" in source, "the CSS layer order must be reversed into the design's"
    assert "unshift(colour)" in source, "background-color paints underneath every image"
    assert "gradient\\(" in source, "a url() layer is an image, not a paint this side can compare"


def test_a_gradient_parses_into_its_kind_stops_and_axis() -> None:
    gradient = parse_gradient("linear-gradient(90deg, rgba(98, 70, 229, 1) 0%, rgba(155, 98, 192, 1) 91%)")

    assert gradient is not None
    assert gradient["kind"] == "linear-gradient"
    assert gradient["angle"] == 90.0
    assert gradient["stops"] == [("rgba(98, 70, 229, 1)", 0.0), ("rgba(155, 98, 192, 1)", 91.0)]


def test_a_stop_list_survives_the_commas_inside_a_colour_function() -> None:
    """`rgba(98, 70, 229, 1)` carries its own commas; a plain split loses every stop."""
    gradient = parse_gradient(
        "linear-gradient(90deg, rgba(1, 2, 3, 1) 0%, rgba(4, 5, 6, 1) 50%, rgba(7, 8, 9, 1) 100%)"
    )

    assert gradient is not None
    assert len(gradient["stops"]) == 3


def test_a_conic_gradient_keeps_its_axis_and_offset() -> None:
    gradient = parse_gradient(
        "conic-gradient(from 114deg at 68% 42%, rgba(142, 64, 250, 1) 7%, rgba(238, 94, 254, 1) 28%)"
    )

    assert gradient is not None
    assert gradient["angle"] == 114.0
    assert len(gradient["stops"]) == 2


def test_a_non_gradient_or_an_unreadable_one_is_an_absence() -> None:
    assert parse_gradient("#FFFFFF") is None
    assert parse_gradient("rgb(1, 2, 3)") is None
    assert parse_gradient("none") is None
    assert parse_gradient(None) is None
    # A gradient whose stops cannot be read must go unverified, never score as a match.
    assert parse_gradient("linear-gradient(90deg, salmon 0%, teal 100%)") is None


def test_the_two_serialisations_of_one_gradient_agree() -> None:
    """Figma writes `rgba(.., 1)`, Chrome writes `rgb(..)`. Same paint, same number."""
    report = build_report(
        {"cta": _design(bg="linear-gradient(90deg, rgba(98, 70, 229, 1) 0%, rgba(155, 98, 192, 1) 91%)")},
        {"cta": _design(bg="linear-gradient(90deg, rgb(98, 70, 229) 0%, rgb(155, 98, 192) 91%)")},
        backend="figma",
    )

    bg = [m for m in report.measurements if m.category == "bg_color"]
    assert bg[0].verified and bg[0].passed
    assert bg[0].deviation == 0.0


def test_a_flat_colour_in_place_of_a_gradient_is_a_mismatch_not_an_absence() -> None:
    """The §6.1 failure verbatim: gradient design, solid implementation, a PASS.

    The category used to be recorded unverified, which made it invisible to all three
    conditions — so the run passed by not looking rather than by matching.
    """
    report = build_report(
        {"cta": _design(bg="linear-gradient(90deg, rgba(98, 70, 229, 1) 0%, rgba(155, 98, 192, 1) 91%)")},
        {"cta": _design(bg="rgb(233, 240, 28)")},
        backend="figma",
    )

    bg = [m for m in report.measurements if m.category == "bg_color"]
    assert bg[0].verified and not bg[0].passed
    assert "bg_color" not in report.unverified_categories


def test_a_gradient_that_differs_structurally_is_a_mismatch() -> None:
    base = "linear-gradient(90deg, rgb(98, 70, 229) 0%, rgb(155, 98, 192) 91%)"
    variants = {
        "rotated axis": base.replace("90deg", "180deg"),
        "moved stop": base.replace("91%", "50%"),
        "extra stop": base.replace("91%", "91%, rgb(0, 0, 0) 100%"),
        "other kind": base.replace("linear-gradient", "radial-gradient"),
    }

    for label, variant in variants.items():
        report = build_report({"cta": _design(bg=base)}, {"cta": _design(bg=variant)}, backend="figma")
        bg = [m for m in report.measurements if m.category == "bg_color"]
        assert bg[0].verified and not bg[0].passed, label


def test_a_near_identical_gradient_still_passes() -> None:
    """The comparison needs a tolerance, or every real gradient would fail."""
    report = build_report(
        {"cta": _design(bg="linear-gradient(90deg, rgb(98, 70, 229) 0%, rgb(155, 98, 192) 91%)")},
        {"cta": _design(bg="linear-gradient(91deg, rgb(98, 70, 229) 0%, rgb(155, 98, 192) 92%)")},
        backend="figma",
    )

    bg = [m for m in report.measurements if m.category == "bg_color"]
    assert bg[0].verified and bg[0].passed


# --- Comparison --------------------------------------------------------------


def _design(**overrides):
    """A complete, comparable fact record — the shape both extractors aim to emit.

    `coord_frame` is declared because positions are only comparable inside a frame:
    without it the engine refuses to difference the origins, so `position` would be
    unverified and every score computed from this fixture would be weights-shifted.
    """
    base = {
        "coord_frame": "parent",
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
        "gap": [24.0, 24.0],
        "font_family": "Poppins",
        "opacity": 1.0,
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
    ≥ 8.0 score rule. Padding (4 axes × ×2), radius (4 axes × ×1.5) and gap
    (2 axes × ×1.5) at the limit therefore cost 8 + 6 + 3 of the 41 total weight,
    leaving 6.6/10.
    """
    actual = dict(_design(padding=[16.0, 28.0, 16.0, 28.0], radius=[6.0, 6.0, 6.0, 6.0]))
    report = build_report({"cta": _design()}, {"cta": actual}, backend="openpencil")

    padding = [m for m in report.measurements if m.category == "padding"]
    assert [m.passed for m in padding] == [True] * 4  # exactly at 4px = still acceptable
    assert report.within_tolerance_pct == 1.0
    assert report.score == 6.6
    assert report.verdict == VERDICT_FAIL


def test_a_single_critical_deviation_over_8px_fails_despite_a_high_score() -> None:
    """The gate's third PASS condition: one bad CTA fails the run outright."""
    actual = dict(_design(padding=[32.0, 24.0, 12.0, 24.0]))  # 20px off on padding-top
    report = build_report({"cta": _design()}, {"cta": actual}, backend="openpencil")

    assert report.max_critical_deviation_px is not None
    assert report.max_critical_deviation_px > PASS_CRITICAL_MAX_DEVIATION_PX
    assert report.verdict == VERDICT_FAIL
    assert "critical deviation" in report.reason


def test_a_critical_colour_mismatch_is_a_deviation_not_only_a_flag() -> None:
    """A ×2 row measured in ΔE still owns condition 3.

    `fg_color` carries `MAX_DELTA_E`, not a pixel budget, so it is absent from
    `critical_categorical_misses` — that set is the rows carrying *no* tolerance.
    The critical-deviation budget is therefore its only escalation, and a version of
    it that aggregated just the px-tolerance rows let a white heading on a dark hero
    keep its score.
    """
    actual = dict(_design(fg="#FFFFFF"))
    report = build_report({"cta": _design()}, {"cta": actual}, backend="openpencil")

    assert [m.passed for m in report.measurements if m.category == "fg_color"] == [False]
    assert report.max_critical_deviation_px is not None
    assert report.max_critical_deviation_px > PASS_CRITICAL_MAX_DEVIATION_PX
    assert report.verdict == VERDICT_FAIL


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


def test_gap_is_compared_on_both_axes() -> None:
    """#14 is the two-axis form of the sibling spacing #3 describes."""
    report = build_report(
        {"grid": _design(gap=[24.0, 12.0])},
        {"grid": _design(gap=[24.0, 18.0])},
        backend="figma",
    )

    gap = [m for m in report.measurements if m.category == "gap"]
    assert [m.axis for m in gap] == ["row", "column"]
    assert [m.verified for m in gap] == [True, True]
    assert [m.deviation for m in gap] == [0.0, 6.0]  # 6px is outside the 4px tolerance
    assert [m.passed for m in gap] == [True, False]


def test_a_uniform_design_gap_broadcasts_to_both_axes() -> None:
    report = build_report({"grid": _design(gap=[16.0])}, {"grid": _design(gap=[16.0, 16.0])}, backend="figma")

    gap = [m for m in report.measurements if m.category == "gap"]
    assert [m.design for m in gap] == [16.0, 16.0]


def test_a_container_verifies_padding_against_its_declared_zero() -> None:
    """End to end from the real `.op` fixture, and the reason #14 alone was not enough.

    The container declares no padding, which means it has none. Measuring that zero
    is what lets `padding` — the gate's highest-weight critical category — be
    verified at all on an auto-layout screen; before this its absence escalated to
    INCONCLUSIVE and no such screen could ever reach a verdict.

    The PASS here is honest but narrow, and `coverage` is what says so: this
    document's only comparable properties are padding, background and gap.
    """
    facts = parse_op_facts(OP_FIXTURE, ["n2"])
    report = build_report({"card": facts["n2"]}, {"card": dict(facts["n2"])}, backend="openpencil")

    padding = [m for m in report.measurements if m.category == "padding"]
    assert padding and all(m.verified for m in padding)
    assert "padding" not in report.unverified_categories
    assert report.verdict == VERDICT_PASS
    assert report.coverage < 0.25  # disclosed rather than hidden: most of §1 was out of scope


def test_an_unverified_critical_category_forces_inconclusive() -> None:
    """PASS while blind to a ×2 category would claim a check that never ran."""
    design = _design()
    del design["padding"]
    report = build_report({"cta": design}, {"cta": _design()}, backend="figma")

    assert "padding" in CRITICAL_CATEGORY_KEYS
    assert report.verdict == VERDICT_INCONCLUSIVE
    assert "padding" in report.reason


def test_a_critical_category_the_dom_side_never_supplied_escalates_too() -> None:
    """*Which* side stayed silent must not decide whether the gate escalates.

    The rule used to key on `absent_from_design`, so a caller that simply did not
    collect `font-family` from the DOM produced `not_comparable` — treated as
    harmless — while the identical blindness on the design side escalated. Skipping a
    measurement must not be a way to opt out of being measured.
    """
    actual = _design()
    del actual["font_family"]
    report = build_report({"h": _design()}, {"h": actual}, backend="figma")

    assert "font_family" in report.unverified_categories
    assert report.verdict == VERDICT_INCONCLUSIVE
    assert "font_family" in report.reason


def test_inapplicability_still_explains_a_frame_without_a_font() -> None:
    """The escalation must not swallow the case it was narrowed for.

    A frame cannot carry typography, so a frame-only screen has nothing to measure it
    on — that is "nothing to check", not "blind", and treating them the same made the
    gate block every ship instead of gating one.
    """
    frame = {"kind": "frame", "padding": [10.0, 20.0, 10.0, 20.0], "bg": "#FFFFFF"}
    report = build_report({"f": frame}, {"f": dict(frame)}, backend="openpencil")

    assert "font_family" in report.unverified_categories
    assert report.verdict == VERDICT_PASS


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
    text = {
        "kind": "text",
        "font_size": 14.0,
        "font_weight": 400.0,
        "font_family": "Poppins",
        "fg": "#000000",
    }
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


# --- Position is only comparable inside a declared frame ----------------------


def test_a_position_is_refused_when_the_two_sides_use_different_origins() -> None:
    """Design parent-relative vs DOM viewport-relative is not a layout defect.

    A root design frame sits at its own origin while the DOM reports the element's
    position in the viewport. Differencing them measures the distance between two
    unrelated origins: the number looks confident, means nothing, and at ×1.5 it can
    drag the run under the within-tolerance floor on its own.
    """
    design = _design(box_origin={"x": 0.0, "y": 0.0}, coord_frame="parent")
    actual = _design(box_origin={"x": 480.0, "y": 220.0}, coord_frame="viewport")
    report = build_report({"cta": design}, {"cta": actual}, backend="figma")

    assert report.verdict == VERDICT_PASS  # not the false FAIL this used to produce
    assert all(not m.verified for m in report.measurements if m.category == "position")
    assert any(s["reason"] == "coord_frame_mismatch" for s in report.skipped_categories)
    assert "position" in report.unverified_categories


def test_a_position_without_a_declared_frame_is_not_compared() -> None:
    """A comparison that cannot be shown to be meaningful is not one."""
    design = _design()
    del design["coord_frame"]
    report = build_report({"cta": design}, {"cta": _design()}, backend="figma")

    assert all(not m.verified for m in report.measurements if m.category == "position")
    assert any(s["reason"] == "coord_frame_undeclared" for s in report.skipped_categories)


def test_a_matching_declared_frame_permits_the_comparison() -> None:
    """The guard must not become a way to never check position at all."""
    report = build_report({"cta": _design()}, {"cta": _design(box_origin={"x": 480.0, "y": 250.0})})

    origin = [m for m in report.measurements if m.category == "position"]
    assert origin and all(m.verified for m in origin)
    assert [m.deviation for m in origin] == [0.0, 30.0]


# --- Viewport binding --------------------------------------------------------


def test_a_viewport_mismatch_is_refused_rather_than_scored() -> None:
    """375-vs-1440 does not make the numbers slightly wrong; it makes them meaningless."""
    design_map = {"cta": {"design_node": "12:345", "selector": "#cta"}}
    facts = {"12:345": _design()}

    with pytest.raises(ValueError, match="viewport mismatch"):
        run_check(design_map, facts, {"#cta": _design()}, design_viewport=375, dom_viewport=1440)


def test_an_undeclared_viewport_is_recorded_not_assumed() -> None:
    design_map = {"cta": {"design_node": "12:345", "selector": "#cta"}}
    facts = {"12:345": _design()}

    bound = run_check(design_map, facts, {"#cta": _design()}, design_viewport=1440, dom_viewport=1440)
    assert bound.viewport_binding == "ok"
    assert bound.design_viewport == 1440

    silent = run_check(design_map, facts, {"#cta": _design()})
    assert silent.viewport_binding == "undeclared"
    assert silent.design_viewport is None


# --- Coverage ----------------------------------------------------------------


def test_coverage_counts_the_gate_surface_not_the_measurement_rows() -> None:
    """`verified categories / producible categories`, so the figure is comparable.

    A row-level ratio would be dominated by normal inapplicability — a frame has no
    font, most text nodes carry no padding row — and would report roughly the same
    number for a thorough run and a nearly blind one.
    """
    report = build_report({"cta": _design()}, {"cta": _design()}, backend="figma")

    # 16 of the 18 producible categories. `asset` is opt-in and this map asks for nothing, so
    # it is genuinely unchecked rather than unchecked-able; `line_count` is unchecked because
    # the fixture is not a hugging text box, which is the normal case for a CTA — #18 is
    # stated only where wrapping is impossible (§4.2).
    assert report.coverage == round(16 / 18, 4)
    assert report.unverified_categories == ["asset", "line_count"], "listed in §1 order"


def test_the_unreachable_categories_leave_coverage_but_not_the_report() -> None:
    """Excluding a category from the denominator must not make it disappear.

    `margin` cannot be stated by any reference side, so charging it to every run is a
    constant loss no work can recover — but dropping it silently would be a smaller version
    of the lie this gate exists to refuse: a surface nobody measured, reported as complete.
    """
    report = build_report({"cta": _design()}, {"cta": _design()}, backend="figma")

    assert report.unreachable_categories == ["margin"]
    assert "margin" not in report.unverified_categories, "excluded from the fraction, named separately"
    assert "margin" not in report.to_json()["unverified_categories"]
    assert report.to_json()["unreachable_categories"] == ["margin"]


def test_the_unreachable_set_only_names_declared_categories() -> None:
    """A typo here would quietly shrink the denominator, which is the one thing the
    exclusion must not be able to do."""
    declared = {spec.key for spec in CATEGORIES}

    assert UNREACHABLE_CATEGORY_KEYS <= declared
    assert UNREACHABLE_CATEGORY_KEYS, "an empty exclusion set would make the test meaningless"


@pytest.mark.parametrize("key", sorted(UNREACHABLE_CATEGORY_KEYS))
def test_no_reference_side_states_an_unreachable_category(key: str) -> None:
    """The claim is "no design extractor has a code path for this", so the test reads them.

    The scan looks for an *emission* — a dict subscript or a mapping key — not for the word,
    so a comment discussing `margin` does not fail this. Implementing reference-side support
    fails the build here, which is the point: the exclusion would then be subtracting a
    comparison the gate can actually make.
    """
    emission = re.compile(rf"""(\[\s*["']{key}["']\s*\]|\b{key}\s*:)""")
    source = (Path(__file__).resolve().parent.parent / "che_core" / "pixel_sources.py").read_text(encoding="utf-8")

    assert not emission.search(source), f"a design extractor now emits `{key}` — drop it from UNREACHABLE_CATEGORY_KEYS"


@pytest.mark.parametrize("key", sorted(UNREACHABLE_CATEGORY_KEYS))
def test_the_implementation_side_does_measure_an_unreachable_category(key: str) -> None:
    """The other half of the claim, and the reason this is not a dead row.

    The DOM extractor *does* collect it — the measurement exists and only its counterpart is
    missing. If that ever stopped being true the category would be dead weight on both
    sides, which is a different decision from the one recorded here.
    """
    extractor = (
        Path(__file__).resolve().parent.parent / "domains" / "ux" / "gates" / "assets" / "dom-facts-extractor.js"
    )
    source = extractor.read_text(encoding="utf-8")

    assert re.search(rf"""\b{key}\s*:""", source), f"the DOM extractor no longer measures `{key}`"


def test_unverified_categories_name_what_a_pass_did_not_check() -> None:
    """`score=9.5 status=PASS` must not be quotable as "everything was checked"."""
    text_only = {"kind": "text", "font_size": 14.0}
    report = build_report({"label": text_only}, {"label": dict(text_only)})

    assert "padding" in report.unverified_categories
    assert report.coverage == round(1 / 18, 4)
    assert report.verdict == VERDICT_INCONCLUSIVE  # padding is ×2 and no element measured it

    line = summarise(report)
    assert " coverage=" in line
    assert "unverified=" in line
    assert "padding" in line
    # The distinction §2.6 draws is only useful if the summary keeps it: a reader who
    # saw `margin` merged into `unverified` would look for work that does not exist.
    assert "unreachable=margin" in line
    assert "margin" not in report.unverified_categories


def test_the_unreachable_token_is_omitted_when_there_is_nothing_to_disclose() -> None:
    """A token that is always present reads as boilerplate and stops being read.

    §2.6 promises `unreachable` alongside the other two "when the held-back set is
    non-empty", so the empty case is part of the contract rather than an accident.
    """
    text_only = {"kind": "text", "font_size": 14.0}
    report = build_report({"label": text_only}, {"label": dict(text_only)})
    report.unreachable_categories = []

    assert "unreachable=" not in summarise(report)


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
        "--design-viewport",
        "1440",
        "--dom-viewport",
        "1440",
        "--out",
        str(out),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["verdict"] == VERDICT_PASS
    assert payload["thresholds"]["pass_score_min"] == PASS_SCORE_MIN
    assert payload["summary"].startswith("[DOMAIN-GATE-EXECUTED] domain=ux gate=pixel-check-gate")
    # The two declarations a reviewer needs to judge how much the PASS is worth.
    assert payload["viewport_binding"] == "ok"
    assert payload["coverage"] is not None
    assert "position" in payload["unverified_categories"]  # `.op` has no coordinates


def test_cli_refuses_a_design_source_without_a_backend(tmp_path: Path) -> None:
    """The backend is never inferred from the file: guessing picks the wrong extractor."""
    design_map = _write(tmp_path / "map.json", {"a": {"design_node": "n1", "selector": "#a"}})
    dom = _write(tmp_path / "dom.json", {})

    proc = _run_cli("pixel", "check", "--map", design_map, "--dom", dom, "--design-source", str(OP_FIXTURE))

    assert proc.returncode == 2
    assert "--design-backend" in proc.stderr


def test_cli_refuses_a_viewport_mismatch_as_a_usage_error(tmp_path: Path) -> None:
    """Refused, not scored: a mismatch invalidates every measurement, not one row."""
    design_map = _write(tmp_path / "map.json", {"hero": {"design_node": "n1", "selector": "#hero"}})
    dom = _write(
        tmp_path / "dom.json",
        {"#hero": {"kind": "frame", "coord_frame": "viewport", "padding": [1.0, 1.0, 1.0, 1.0]}},
    )

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
        "--design-viewport",
        "375",
        "--dom-viewport",
        "1440",
    )

    assert proc.returncode == 2
    assert "viewport mismatch" in proc.stderr


def test_cli_reports_an_unreadable_artefact_as_a_usage_error(tmp_path: Path) -> None:
    design_map = _write(tmp_path / "map.json", {})

    proc = _run_cli("pixel", "check", "--map", design_map, "--dom", str(tmp_path / "nope.json"), "--design", design_map)

    assert proc.returncode == 2
    assert "cannot read" in proc.stderr


# --- A declared backend without an extractor (penpot) ------------------------
#
# `domains/ux/connectors/penpot.config.md` presents Penpot as a first-class alternative to
# Figma, so "unknown design backend" would be a lie about the caller's request and would
# send them looking for a spelling error that does not exist. These tests pin the two
# refusals apart, because collapsing them is precisely the defect being fixed.


def test_the_declared_backends_are_split_into_implemented_and_not() -> None:
    """One set per meaning, so no caller has to guess which is which."""
    assert BACKENDS_WITH_EXTRACTOR.isdisjoint(BACKENDS_WITHOUT_EXTRACTOR)
    assert set(DECLARED_BACKENDS) == BACKENDS_WITH_EXTRACTOR | BACKENDS_WITHOUT_EXTRACTOR


def test_a_declared_backend_without_an_extractor_is_refused_by_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no extractor"):
        resolve_design_source(tmp_path / "session.json", "penpot", [])


def test_a_typo_is_still_reported_as_a_typo(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown design backend"):
        resolve_design_source(tmp_path / "session.json", "penopt", [])


def test_cli_refuses_a_penpot_source_with_a_reason_not_a_choice_error(tmp_path: Path) -> None:
    design_map = _write(tmp_path / "map.json", {"a": {"design_node": "n1", "selector": "#a"}})
    dom = _write(tmp_path / "dom.json", {})

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
        "penpot",
    )

    assert proc.returncode == 2
    assert "no extractor" in proc.stderr
    # The whole point: the argument parser must not get to answer this one.
    assert "invalid choice" not in proc.stderr


def test_cli_accepts_a_declared_backend_as_provenance_for_a_pre_keyed_bag(tmp_path: Path) -> None:
    """With `--design` the engine reads no design source, so the label is provenance only.

    Refusing it there would force the caller to write `figma` on a bag that did not come
    from Figma — a report wrong about its own origin, in exchange for nothing.
    """
    design_map = _write(tmp_path / "map.json", {"hero": {"design_node": "n1", "selector": "#hero"}})
    facts = parse_op_facts(OP_FIXTURE, ["n1"])
    design = _write(tmp_path / "design.json", {"n1": facts["n1"]})
    dom = _write(tmp_path / "dom.json", {"#hero": facts["n1"]})

    proc = _run_cli(
        "pixel",
        "check",
        "--map",
        design_map,
        "--dom",
        dom,
        "--design",
        design,
        "--design-backend",
        "penpot",
    )

    assert proc.returncode == 0, proc.stderr
    assert "backend=penpot" in proc.stdout


# --- Typography family and opacity (#15, #16) --------------------------------


def test_both_parsers_read_a_font_family() -> None:
    """#15 exists because a wrong typeface with matching metrics scored 100 % (§6.1)."""
    figma = parse_figma_facts(FIGMA_FIXTURE.read_text(encoding="utf-8"), ["I117:5864;1:12255"])
    op = parse_op_facts(OP_FIXTURE, ["n4"])

    assert figma["I117:5864;1:12255"]["font_family"] == "Poppins"
    assert op["n4"]["font_family"] == "Noto Sans SC"


def test_only_the_bridge_defaults_an_absent_opacity_to_fully_opaque() -> None:
    """`opacity` omitted means 1.0 in the bridge; `.op` cannot express it at all.

    Asserting 1.0 where the format has no such key would be fabricating a
    measurement, so `.op` emits nothing and the category stays unverified.
    """
    figma = parse_figma_facts(FIGMA_FIXTURE.read_text(encoding="utf-8"), ["I117:5864;1:12255", "117:5851"])
    op = parse_op_facts(OP_FIXTURE, ["n1"])

    assert figma["I117:5864;1:12255"]["opacity"] == 1.0  # omitted -> opaque
    assert figma["117:5851"]["opacity"] == pytest.approx(0.4, abs=1e-6)  # explicit -> read as-is
    assert "opacity" not in op["n1"]


def test_a_family_is_compared_by_its_first_name_not_the_whole_stack() -> None:
    """The DOM resolves a stack while the design names one family.

    Differencing the raw strings would fail every text node, which is a fabricated
    FAIL rather than a measurement.
    """
    report = build_report(
        {"h": _design(font_family="Volkhov")},
        {"h": _design(font_family='Volkhov, "Volkhov Fallback", serif')},
        backend="figma",
    )

    family = [m for m in report.measurements if m.category == "font_family"]
    assert family[0].verified and family[0].passed
    assert family[0].design == family[0].actual == "volkhov"


def test_an_unreadable_family_is_an_absence_not_a_mismatch() -> None:
    """A stack we cannot read is not evidence that the font is wrong."""
    report = build_report({"h": _design(font_family="Poppins")}, {"h": _design(font_family=None)}, backend="figma")

    family = [m for m in report.measurements if m.category == "font_family"]
    assert not family[0].verified
    assert any(s["category"] == "font_family" and s["reason"] == "not_comparable" for s in report.skipped_categories)


def test_an_opacity_drift_is_measured_and_tolerated_to_four_percent() -> None:
    inside = build_report({"h": _design(opacity=0.4)}, {"h": _design(opacity=0.43)}, backend="figma")
    outside = build_report({"h": _design(opacity=0.4)}, {"h": _design(opacity=0.6)}, backend="figma")

    assert all(m.verified for m in inside.measurements if m.category == "opacity")
    assert [m.passed for m in inside.measurements if m.category == "opacity"] == [True]
    assert [m.passed for m in outside.measurements if m.category == "opacity"] == [False]


# --- §3 condition 3, for the categories that carry no tolerance --------------


def test_a_wrong_typeface_or_weight_fails_despite_a_score_that_would_have_passed() -> None:
    """Condition 3's 8px budget only describes the px categories.

    A category with no tolerance is wrong or it is not — there is no such thing as
    "3px of the wrong typeface" — and its deviation is a flag, so it could never
    exceed 8. Before this rule a single mismatched ×2 category cost ~2 of 41 weight
    and left the score at 9.5, inside every numeric condition: the run passed while
    rendering the wrong font. `font_weight` had carried that hole since the gate was
    written, and #15 would have inherited it.
    """
    family = build_report({"h": _design(font_family="Volkhov")}, {"h": _design(font_family="Poppins")}, backend="figma")
    weight = build_report({"h": _design(font_weight=600.0)}, {"h": _design(font_weight=400.0)}, backend="figma")

    for report in (family, weight):
        assert report.score is not None and report.score >= PASS_SCORE_MIN  # the score alone would have passed
        assert report.verdict == VERDICT_FAIL
        assert "critical mismatch" in report.reason


def test_a_toleranced_critical_category_inside_its_budget_is_still_not_a_mismatch() -> None:
    """The new rule must not swallow the px categories it was never about."""
    report = build_report({"h": _design(padding=[14.0, 24.0, 12.0, 24.0])}, {"h": _design()}, backend="figma")

    assert report.verdict == VERDICT_PASS
    assert "critical mismatch" not in report.reason


# --- The retry budget (§5) ---------------------------------------------------


def test_a_third_attempt_is_refused_rather_than_run() -> None:
    """A pixel gate is a measure → edit → measure loop whose only natural stop is a
    verdict, and an INCONCLUSIVE verdict never supplies one. Nothing inside the loop
    bounds it, so the budget is enforced at the runner instead of promised in prose."""
    design_map = {"cta": {"design_node": "12:345", "selector": "#cta"}}
    facts = {"12:345": _design()}

    with pytest.raises(ValueError, match="retry budget"):
        run_check(design_map, facts, {"#cta": _design()}, attempt=3)


def test_a_recorded_override_is_the_only_way_past_the_budget() -> None:
    design_map = {"cta": {"design_node": "12:345", "selector": "#cta"}}
    facts = {"12:345": _design()}

    report = run_check(
        design_map,
        facts,
        {"#cta": _design()},
        attempt=3,
        override_reason="EXPLICIT_OVERRIDE domain=ux gate=pixel-check-gate reason=user accepted the drift",
    )

    assert report.attempt == 3
    assert "override=" in summarise(report)


def test_the_report_carries_the_input_digests_that_tell_a_retry_from_a_moved_check() -> None:
    design_map = {"cta": {"design_node": "12:345", "selector": "#cta"}}
    facts = {"12:345": _design()}

    report = run_check(
        design_map,
        facts,
        {"#cta": _design()},
        attempt=2,
        design_map_sha256="a" * 64,
        design_source_sha256="b" * 64,
    )
    payload = report.to_json()

    assert payload["attempt"] == 2
    assert payload["design_map_sha256"] == "a" * 64
    assert payload["design_source_sha256"] == "b" * 64
    assert payload["override_reason"] == ""


def test_cli_refuses_a_third_attempt_as_a_usage_error(tmp_path: Path) -> None:
    design_map = _write(tmp_path / "map.json", {"hero": {"design_node": "n1", "selector": "#hero"}})
    facts = parse_op_facts(OP_FIXTURE, ["n1"])
    dom = _write(tmp_path / "dom.json", {"#hero": facts["n1"]})

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
        "--attempt",
        "3",
    )

    assert proc.returncode == 2
    assert "retry budget" in proc.stderr


def test_cli_records_the_attempt_and_the_digests_of_what_it_compared(tmp_path: Path) -> None:
    design_map = _write(tmp_path / "map.json", {"hero": {"design_node": "n1", "selector": "#hero"}})
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
        "--attempt",
        "2",
        "--out",
        str(out),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["attempt"] == 2
    assert len(payload["design_map_sha256"]) == 64
    assert len(payload["design_source_sha256"]) == 64
    assert "attempt=2" in payload["summary"]


# --- Asset identity (#17) ----------------------------------------------------


def _digest(char: str) -> str:
    return char * 64


def test_a_map_entry_may_declare_the_asset_the_element_must_serve() -> None:
    design_map = {"hero-icon": {"design_node": "12:400", "selector": "#icon", "asset_sha256": _digest("b")}}

    design, _ = join_by_map(design_map, {"12:400": _design()}, {})

    assert design["hero-icon"]["asset_sha256"] == _digest("b")


def test_an_asset_digest_that_is_not_a_digest_is_rejected() -> None:
    """A 63-character typo would otherwise report as a *mismatch* against a good file."""
    design_map = {"hero-icon": {"design_node": "12:400", "selector": "#icon", "asset_sha256": "b" * 63}}

    with pytest.raises(ValueError, match="asset_sha256"):
        join_by_map(design_map, {"12:400": _design()}, {})


def test_a_wrong_asset_fails_the_run() -> None:
    """The §6.1 hole verbatim: a wrong icon in the right box used to score perfectly."""
    design_map = {"hero-icon": {"design_node": "12:400", "selector": "#icon", "asset_sha256": _digest("b")}}
    report = run_check(
        design_map,
        {"12:400": _design()},
        {"#icon": _design(asset_sha256=_digest("c"))},
        backend="figma",
    )

    asset = [m for m in report.measurements if m.category == "asset"]
    assert asset[0].verified and not asset[0].passed
    assert report.verdict == VERDICT_FAIL
    assert "critical mismatch" in report.reason


def test_the_right_asset_verifies() -> None:
    design_map = {"hero-icon": {"design_node": "12:400", "selector": "#icon", "asset_sha256": _digest("b")}}
    report = run_check(
        design_map,
        {"12:400": _design()},
        {"#icon": _design(asset_sha256=_digest("b"))},
        backend="figma",
    )

    asset = [m for m in report.measurements if m.category == "asset"]
    assert asset[0].verified and asset[0].passed


def test_an_element_that_declares_no_asset_is_not_asked_for_one() -> None:
    """Opt-in: the default state must not escalate, or every map would have to declare a
    digest for every element and the escalation would become noise rather than signal."""
    design_map = {"cta": {"design_node": "12:345", "selector": "#cta"}}
    report = run_check(design_map, {"12:345": _design()}, {"#cta": _design()}, backend="figma")

    assert report.verdict == VERDICT_PASS
    assert "asset" in report.unverified_categories
    asset_skips = [s for s in report.skipped_categories if s["category"] == "asset"]
    assert asset_skips and all(s["reason"] == "not_applicable" for s in asset_skips)


def test_an_asset_declared_but_never_measured_escalates() -> None:
    """Declaring the check and then not collecting the digest is blindness, not opt-out."""
    design_map = {"hero-icon": {"design_node": "12:400", "selector": "#icon", "asset_sha256": _digest("b")}}
    report = run_check(design_map, {"12:400": _design()}, {"#icon": _design()}, backend="figma")

    assert report.verdict == VERDICT_INCONCLUSIVE
    assert "asset" in report.reason


def test_an_exact_category_the_dom_side_omitted_is_an_absence_not_a_mismatch() -> None:
    """A value nobody measured must not be convicted.

    `font_weight` compared `600.0` against `None`, found them unequal and reported a
    confident FAIL — a mismatch the run had no evidence for.
    """
    actual = _design()
    del actual["font_weight"]
    report = build_report({"h": _design()}, {"h": actual}, backend="figma")

    weight = [m for m in report.measurements if m.category == "font_weight"]
    assert not weight[0].verified
    assert any(s["category"] == "font_weight" and s["reason"] == "not_comparable" for s in report.skipped_categories)
    assert report.verdict == VERDICT_INCONCLUSIVE  # and it escalates, because it is ×2


# --- §4.1 the committed reference record -------------------------------------


def test_the_design_record_is_keyed_by_element_in_the_engine_vocabulary() -> None:
    """§4.1 "text and git-diffable" is only true if the file holds the numbers that were
    compared. It is the flat vocabulary the extractors emit — a nested presentation
    (`w`/`h`, `border: {…}`, `font: {…}`) would be a second schema to keep in sync, and the
    reviewer's copy could then disagree with the scored values."""
    design_map = {"hero-frame": {"design_node": "n1", "selector": "[data-design-node='n1']"}}
    facts = parse_op_facts(OP_FIXTURE, ["n1"])

    record = design_facts_record(design_map, facts, "lg")

    assert set(record) == {"hero-frame"}
    entry = record["hero-frame"]
    assert entry["design_node"] == "n1"
    assert entry["selector"] == "[data-design-node='n1']"
    assert entry["breakpoint"] == "lg"
    assert entry["facts"]["padding"] == [88.0, 84.0, 88.0, 84.0]
    assert "w" not in entry["facts"] and "font" not in entry["facts"]


def test_an_element_whose_node_was_not_extracted_keeps_an_empty_record() -> None:
    """Dropping it would make "the extractor could not read this node" indistinguishable
    from "this element was never mapped" — the difference §2.6 exists to surface."""
    record = design_facts_record({"ghost": {"design_node": "9:999", "selector": "#ghost"}}, {}, "lg")

    assert record["ghost"]["facts"] == {}
    assert record["ghost"]["design_node"] == "9:999"


def test_a_map_entry_that_is_not_an_object_is_skipped() -> None:
    """A malformed map is refused by `join_by_map`; the record must not crash first."""
    record = design_facts_record({"broken": None, "ok": {"design_node": "n1"}}, {}, "")

    assert set(record) == {"ok"}
    assert record["ok"]["selector"] == ""


def test_an_unstated_breakpoint_is_written_as_undeclared() -> None:
    """The report already uses `undeclared` for an unstated dimension; the record must not
    invent a second word for the same absence."""
    record = design_facts_record({"e": {"design_node": "n1"}}, {}, "")

    assert record["e"]["breakpoint"] == "undeclared"


def test_the_design_record_echoes_a_declared_asset_digest() -> None:
    """#17's expectation is declared on the map, not extracted — but it *is* compared, so a
    reader of the record would otherwise have to open a second file to find the only key
    that makes an asset row verifiable."""
    design_map = {"icon": {"design_node": "n1", "selector": "#icon", "asset_sha256": _digest("a")}}

    record = design_facts_record(design_map, {"n1": _design()}, "lg")

    assert record["icon"]["facts"]["asset_sha256"] == _digest("a")


def test_the_record_matches_the_facts_the_engine_actually_scored() -> None:
    """The strongest form of the guarantee: same keys, same values, no transcription."""
    design_map = {"hero": {"design_node": "n1", "selector": "#hero", "asset_sha256": _digest("c")}}
    design = {"n1": _design()}
    dom = {"#hero": {**_design(), "asset_sha256": _digest("c")}}

    record = design_facts_record(design_map, design, "lg")
    design_elements, _ = join_by_map(design_map, design, dom)

    assert record["hero"]["facts"] == design_elements["hero"]


def test_cli_writes_the_design_record_when_the_run_is_scored(tmp_path: Path) -> None:
    """§4.1's record has to actually reach the disk, inside the worktree, in one command."""
    design_map = _write(
        tmp_path / "lg.map.json", {"hero-frame": {"design_node": "n1", "selector": "[data-design-node='n1']"}}
    )
    facts = parse_op_facts(OP_FIXTURE, ["n1"])
    dom = _write(tmp_path / "dom.json", {"[data-design-node='n1']": facts["n1"]})
    record_path = tmp_path / "lg.design-facts.json"

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
        "--design-facts-out",
        str(record_path),
        "--json",
    )

    assert proc.returncode in (0, 1, 3), proc.stderr  # the record does not depend on the verdict
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["hero-frame"]["facts"]["bg"] == ["#FFF7ED"]


def test_cli_writes_no_design_record_when_the_run_is_refused(tmp_path: Path) -> None:
    """A record of a check that never happened is worse than no record: it reads as evidence."""
    design_map = _write(tmp_path / "lg.map.json", {"hero": {"design_node": "n1", "selector": "#hero"}})
    dom = _write(tmp_path / "dom.json", {"#hero": {"coord_frame": "viewport", "line_height": 24}})
    record_path = tmp_path / "lg.design-facts.json"

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
        "--design-facts-out",
        str(record_path),
    )

    assert proc.returncode == 2
    assert not record_path.exists()
