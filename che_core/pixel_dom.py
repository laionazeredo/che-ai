"""Implementation-side fact-bag contract for gate `ux-pixel-check-gate`.

`che_core/pixel.py` compares whatever it is handed; it has no idea what a DOM fact bag
is supposed to look like. That gap was not theoretical:

* the comparator accepted ``line_height: 24`` — a pixel value — where the design states
  ``1.5``, a multiplier, and scored it as an enormous deviation. The run failed loudly
  for a reason that was entirely the caller's mistake;
* a property could simply be omitted, and the only trace was a category quietly leaving
  ``verified``. Nothing said "you forgot to collect this".

Both are *shape* errors, not disagreements about a design, and both are invisible from
inside the comparator. So this module is the boundary: the contract §4.2 documents, as
code, enforced before a run is scored rather than assumed after it is believed.

Deliberately **not** here: whether the DOM element exists, whether it matches the design,
or anything else that is a real finding. A problem returned from this module is always
something the caller can fix by measuring again — never a verdict.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List, Tuple

from che_core.pixel import parse_color

#: The five axes of one shadow (§1 #12). A shadow missing any of them cannot be compared.
SHADOW_AXES = ("x", "y", "blur", "spread", "alpha")

#: Plausible bands for the two ratio-valued categories. A reading outside one of these is
#: almost always an unnormalised pixel value rather than a design disagreement: the design
#: states `line-height: 1.5`, so a `line_height` of 24 can only mean the browser's px
#: reading was handed over raw.
_LINE_HEIGHT_BAND = (0.5, 5.0)
_LETTER_SPACING_BAND = (-0.5, 0.5)

_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")

#: Four-sided properties, in the order the gate compares them.
_FOUR_SIDED = ("padding", "margin", "radius")
#: Two-axis properties (row, column) — §1 #14.
_TWO_AXIS = ("gap",)
#: Boxes that must be objects of numbers.
_BOXES = ("box_size", "box_origin")
#: Scalar px properties.
_PX_SCALARS = ("border_width", "font_size")

#: Every property this contract inspects. `che_core.pixel.CATEGORIES` must not contain a
#: property outside this set, or a newly added category would silently skip validation —
#: asserted by `tests/test_pixel_dom.py`.
#:
#: Two entries back no category. `coord_frame` is a precondition, not a measurement (§2.3):
#: the comparator reads it to decide whether `position` may be compared at all, so a wrong
#: one yields a meaningless deviation rather than none. `kind` is provenance — it decides
#: whether typography applies to the element. Checking the shape of something nothing compares
#: is still worth doing — a malformed one means the extractor was replaced by something that
#: does not follow §4.2 — but it claims nothing beyond well-formedness, which is why it is
#: stated here rather than left implied.
CHECKED_PROPERTIES = frozenset(
    {
        "kind",
        "coord_frame",
        "box_size",
        "box_origin",
        "border_width",
        "border_color",
        "font_size",
        "font_weight",
        "font_family",
        "line_height",
        "letter_spacing",
        "fg",
        "bg",
        "shadow",
        "opacity",
        "line_count",
        "asset_sha256",
        *_FOUR_SIDED,
        *_TWO_AXIS,
    }
)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _is_number_list(value: Any, allowed_sizes: Tuple[int, ...]) -> bool:
    """A number, or a list of numbers whose length the comparator's coercion can absorb.

    The accepted shapes deliberately mirror `che_core.pixel._as_list`: a bare number
    broadcasts to every side and the CSS two-value shorthand is expanded, so refusing
    either here would reject a bag the engine would have compared correctly. This module's
    job is the shape the *consumer* cannot tolerate, not a stricter contract of its own
    invention — an over-strict validator only moves the same mistake one level down, from a
    scored deviation to a usage error on numbers that were fine.
    """
    if _is_number(value):
        return True
    return isinstance(value, (list, tuple)) and len(value) in allowed_sizes and all(_is_number(v) for v in value)


def _is_paint(value: Any) -> bool:
    """A flat colour or a gradient definition — the two things `fg`/`border_color` may carry."""
    if isinstance(value, str) and "gradient(" in value:
        return True
    return parse_color(value) is not None


def _is_paint_stack(value: Any) -> bool:
    """`bg` as one paint, or an ordered bottom-to-top list of them (§1 #11).

    A stack is only usable if **every** layer is comparable: the comparator pairs layer *n*
    with layer *n*, so one unreadable entry would shift every pair after it and report the
    wrong comparison rather than none. That is the extractor's rule too — see
    `dom-facts-extractor.js` — and it is why an empty list is refused here: it is not a
    background, it is a missing measurement wearing one.
    """
    if isinstance(value, (list, tuple)):
        return len(value) > 0 and all(_is_paint(entry) for entry in value)
    return _is_paint(value)


def _check_record(selector: str, record: Any) -> List[str]:
    problems: List[str] = []

    if not isinstance(record, dict):
        return [f"{selector}: expected an object of facts, found {type(record).__name__}"]

    def bad(message: str) -> None:
        problems.append(f"{selector}: {message}")

    # `coord_frame` is the one declaration the comparator actually reads: without it
    # `position` cannot be shown to be meaningful (§2.3). `kind` is recorded provenance —
    # the applicability rule that keeps a frame's missing font from escalating reads the
    # *design* node's kind — so it is validated when present and never demanded.
    frame = record.get("coord_frame")
    if not isinstance(frame, str) or not frame.strip():
        bad("`coord_frame` is missing — §2.3 requires it, or position cannot be compared")

    if "kind" in record:
        kind = record["kind"]
        if not isinstance(kind, str) or not kind.strip():
            bad(f"`kind`, when present, must be a non-empty string, found {kind!r}")

    for prop in _FOUR_SIDED:
        if prop in record and not _is_number_list(record[prop], (1, 2, 4)):
            bad(f"`{prop}` must be 1, 2 or 4 px numbers (top, right, bottom, left), found {record[prop]!r}")
    for prop in _TWO_AXIS:
        if prop in record and not _is_number_list(record[prop], (1, 2)):
            bad(f"`{prop}` must be 1 or 2 px numbers (row, column), found {record[prop]!r}")

    for prop in _BOXES:
        if prop in record:
            value = record[prop]
            if not isinstance(value, dict) or not value:
                bad(f"`{prop}` must be an object of px numbers, found {value!r}")
            elif any(not _is_number(v) for v in value.values()):
                bad(f"`{prop}` values must be px numbers, found {value!r}")

    for prop in _PX_SCALARS:
        if prop in record and not _is_number(record[prop]):
            bad(f"`{prop}` must be a px number, found {record[prop]!r}")

    if "font_weight" in record:
        weight = record["font_weight"]
        if not _is_number(weight) or not 1 <= float(weight) <= 1000:
            bad(f"`font_weight` must be the numeric weight, found {weight!r}")

    if record.get("line_height") is not None:
        value = record["line_height"]
        if not _is_number(value):
            bad(f"`line_height` must be a number, found {value!r}")
        elif not _LINE_HEIGHT_BAND[0] <= float(value) <= _LINE_HEIGHT_BAND[1]:
            bad(
                f"`line_height` must be the normalised multiplier, not the px reading "
                f"(§1 #8 compares a ratio): found {value!r}"
            )

    if record.get("letter_spacing") is not None:
        value = record["letter_spacing"]
        if not _is_number(value):
            bad(f"`letter_spacing` must be a number, found {value!r}")
        elif not _LETTER_SPACING_BAND[0] <= float(value) <= _LETTER_SPACING_BAND[1]:
            bad(f"`letter_spacing` must be em, not px (§1 #9 tolerance is 0.01em): found {value!r}")

    for prop in ("fg", "border_color"):
        if prop in record and not _is_paint(record[prop]):
            bad(f"`{prop}` is neither a readable colour nor a gradient: {record[prop]!r}")

    if "bg" in record and not _is_paint_stack(record["bg"]):
        bad(
            "`bg` is neither a readable colour, a gradient, nor a non-empty list of them "
            f"(§1 #11 compares a whole paint stack, bottom-to-top): {record['bg']!r}"
        )

    if "opacity" in record:
        value = record["opacity"]
        if not _is_number(value) or not 0.0 <= float(value) <= 1.0:
            bad(f"`opacity` must be between 0 and 1, found {value!r}")

    if "line_count" in record:
        value = record["line_count"]
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            bad(f"`line_count` must be a positive integer, found {value!r}")

    if "asset_sha256" in record:
        value = record["asset_sha256"]
        if not isinstance(value, str) or _DIGEST_RE.match(value) is None:
            bad(f"`asset_sha256` must be 64 lowercase hex characters, found {value!r}")

    if "shadow" in record:
        value = record["shadow"]
        if not isinstance(value, dict) or set(value) != set(SHADOW_AXES):
            bad(f"`shadow` must carry exactly {', '.join(SHADOW_AXES)}, found {value!r}")
        elif any(not _is_number(v) for v in value.values()):
            bad(f"`shadow` values must be numbers, found {value!r}")

    return problems


def validate_dom_facts(dom_facts: Any, expected_selectors: Iterable[str]) -> List[str]:
    """Every problem that makes this bag unusable, as human-readable lines.

    An empty list means the bag is well-formed and the run may be scored. Never returns a
    design disagreement: everything here is fixable by measuring the DOM again, which is
    the only thing that makes it safe to refuse the run outright.

    `expected_selectors` is the set the design map declares. A selector the map names but
    the bag lacks is the highest-value check in this module: the comparator would read it
    as ``missing_from_dom`` and **fail the run** on an element nobody tried to measure.
    """
    if not isinstance(dom_facts, dict):
        return [f"dom facts must be an object keyed by selector, found {type(dom_facts).__name__}"]

    problems: List[str] = []
    for selector in dict.fromkeys(expected_selectors):
        if selector not in dom_facts:
            problems.append(
                f"{selector}: declared in design-map.json but absent from the DOM facts — the "
                "comparator would report `missing_from_dom` and FAIL on a measurement that was "
                "never attempted. Re-run the extractor over the whole map."
            )
    for selector, record in dom_facts.items():
        problems.extend(_check_record(selector, record))
    return problems


def summarise_problems(problems: List[str], limit: int = 6) -> str:
    """One line naming the first few problems, for a usage error."""
    if not problems:
        return ""
    shown = "; ".join(problems[:limit])
    if len(problems) > limit:
        shown += f"; … and {len(problems) - limit} more"
    return shown


def fact_bag_summary(dom_facts: Dict[str, Any]) -> Dict[str, Any]:
    """What the bag declared about itself — carried into the report as provenance.

    The engine cannot tell a caller that collected fifty properties from one that
    collected three; `unverified_categories` shows the consequence but not the cause.
    Recording the declared surface makes the next run's silence distinguishable from
    this one's.
    """
    collected: set = set()
    for record in dom_facts.values():
        if isinstance(record, dict):
            collected.update(key for key, value in record.items() if value is not None)
    return {"elements": len(dom_facts), "properties_collected": sorted(collected)}
