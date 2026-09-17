"""Pixel-check engine — the functional core of gate `ux-pixel-check-gate`.

This module compares a **design reference** against a **live DOM** numerically. It
is the executable half of `domains/ux/gates/pixel-check-gate.md`, whose §1/§2
thresholds, weights, scoring formula and PASS conditions it implements verbatim.
That gate file stays the human-facing SSoT; :data:`CATEGORIES` and
:data:`PASS_RULES` mirror it, and `tests/test_pixel.py` asserts the two agree.

Why properties and not pixels
-----------------------------
The obvious approach — screenshot the page, diff it against an exported design
image — is the wrong instrument. A whole-frame pixel delta is dominated by text
antialiasing, device-pixel-ratio and font-loading noise, while being nearly blind
to a 2px radius error: it inverts the signal-to-noise ratio for exactly the
deviations this gate exists to catch. So the comparison is property against
property, and an image diff is demoted to PR evidence (see the gate's
`tool_evidence_only`).

Fail-closed on unverifiable categories
--------------------------------------
A design source does not always expose every property — for example the Figma
bridge emits no `letterSpacing`, so category #9 cannot be measured from it. A
category with no design value is recorded as **unverified**: it is excluded from
the score (never counted as a pass) and, when it is a ×2 critical category, the
verdict becomes :data:`INCONCLUSIVE` rather than PASS. Reporting PASS while blind
to padding would convert "never checked" into "checked", which is the one failure
mode worse than having no gate.

No I/O beyond reading artefacts handed in by the caller: the MCP calls that fetch
a design and measure a browser happen in the agent, not here, which is what makes
this module testable offline.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from che_core.pixel_sources import (
    BACKENDS_WITH_EXTRACTOR,
    BACKENDS_WITHOUT_EXTRACTOR,
    COORD_FRAME_NONE,
    parse_figma_facts,
    parse_op_facts,
)

# --- Contract constants (mirror the gate §1 tolerances + §2 weights) ---------

WEIGHT_CRITICAL = 2.0
WEIGHT_MEDIUM = 1.5
WEIGHT_STANDARD = 1.0

#: Maximum CIE76 ΔE between two colours that still counts as a match (§1 #5/#10/#11).
MAX_DELTA_E = 5.0

#: `pass_score_min` from the gate frontmatter.
PASS_SCORE_MIN = 8.0
#: `pass_within_tolerance_pct` from the gate frontmatter.
PASS_WITHIN_TOLERANCE_PCT = 0.95
#: `pass_critical_max_deviation_px` from the gate frontmatter.
PASS_CRITICAL_MAX_DEVIATION_PX = 8.0

VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
#: The comparison could not be completed honestly (too little verifiable data).
VERDICT_INCONCLUSIVE = "INCONCLUSIVE"

#: The design source could not be read at all (access, bad node id, no engine).
OUTCOME_SOURCE_UNAVAILABLE = "DESIGN_SOURCE_UNAVAILABLE"

#: Process exit status per verdict, so a caller can branch without parsing text.
_EXIT_CODES = {VERDICT_PASS: 0, VERDICT_FAIL: 1, VERDICT_INCONCLUSIVE: 3}

_KIND_PX = "px"
_KIND_EXACT = "exact"
_KIND_COLOR = "color"
#: An ordered bottom-to-top list of paints. Distinct from `_KIND_COLOR` because a stack is
#: compared layer by layer, and its *length* is itself a finding.
_KIND_PAINT_STACK = "paint_stack"
_KIND_RATIO = "ratio"
_KIND_EM = "em"
_KIND_PX_LIST = "px_list"
_KIND_PX_VEC = "px_vec"
_KIND_SHADOW = "shadow"
_KIND_FAMILY = "family"
_KIND_SCALAR = "scalar"


@dataclass(frozen=True)
class CategorySpec:
    """One measurable property, with the gate's tolerance and weight.

    ``critical`` drives the gate's third PASS condition (a single critical element
    deviating more than 8px fails the gate outright, whatever the mean score).
    """

    key: str
    prop: str
    kind: str
    tolerance: float
    weight: float
    axes: Tuple[str, ...] = ("",)

    @property
    def critical(self) -> bool:
        return self.weight == WEIGHT_CRITICAL


def _c(key: str, prop: str, kind: str, tol: float, weight: float, *axes: str) -> CategorySpec:
    return CategorySpec(key, prop, kind, tol, weight, axes or ("",))


#: The gate's §1 table, row by row. Order matches the gate so a diff is readable.
CATEGORIES: Tuple[CategorySpec, ...] = (
    _c("box", "box_size", _KIND_PX, 4.0, WEIGHT_STANDARD, "width", "height"),
    _c("padding", "padding", _KIND_PX_LIST, 4.0, WEIGHT_CRITICAL, "top", "right", "bottom", "left"),
    _c("margin", "margin", _KIND_PX_LIST, 4.0, WEIGHT_MEDIUM, "top", "right", "bottom", "left"),
    _c("radius", "radius", _KIND_PX_LIST, 2.0, WEIGHT_MEDIUM, "top_left", "top_right", "bottom_right", "bottom_left"),
    _c("border_width", "border_width", _KIND_PX, 1.0, WEIGHT_STANDARD),
    _c("border_color", "border_color", _KIND_COLOR, MAX_DELTA_E, WEIGHT_STANDARD),
    _c("font_size", "font_size", _KIND_PX, 2.0, WEIGHT_CRITICAL),
    _c("font_weight", "font_weight", _KIND_EXACT, 0.0, WEIGHT_CRITICAL),
    _c("line_height", "line_height", _KIND_RATIO, 0.05, WEIGHT_STANDARD),
    _c("letter_spacing", "letter_spacing", _KIND_EM, 0.01, WEIGHT_STANDARD),
    _c("fg_color", "fg", _KIND_COLOR, MAX_DELTA_E, WEIGHT_CRITICAL),
    _c("bg_color", "bg", _KIND_PAINT_STACK, MAX_DELTA_E, WEIGHT_STANDARD),
    _c("shadow", "shadow", _KIND_SHADOW, 2.0, WEIGHT_STANDARD, "x", "y", "blur", "spread", "alpha"),
    _c("position", "box_origin", _KIND_PX_VEC, 8.0, WEIGHT_MEDIUM, "x", "y"),
    # #14–#16 — appended rather than slotted in beside their siblings, because every
    # category in this module and in the gate is cited by its §1 number: renumbering
    # would silently invalidate those references to buy nothing but tidiness.
    _c("gap", "gap", _KIND_PX_LIST, 4.0, WEIGHT_MEDIUM, "row", "column"),
    # A wrong typeface with matching metrics used to score 100 % (§6.1), which is the
    # worst shape a hole can take: a silent PASS rather than a silent gap. It carries
    # the same weight as font-weight, because "the wrong font" is not "almost right".
    _c("font_family", "font_family", _KIND_FAMILY, 0.0, WEIGHT_CRITICAL),
    # ×1 because opacity is routinely absent from a design source: `parse_op_facts` reads it
    # only when the document carries the key, and the sampled documents do not. A critical
    # category the source usually omits would force INCONCLUSIVE on most `.op` screens.
    _c("opacity", "opacity", _KIND_SCALAR, 0.04, WEIGHT_STANDARD),
    # #17 — the §6.1 "a wrong icon in the right box scores perfectly" hole. A digest is
    # exact, so it is ×2 and condition 3 fails the run on any mismatch.
    _c("asset", "asset_sha256", _KIND_EXACT, 0.0, WEIGHT_CRITICAL),
    # #18 — text reflow, which §6.1 used to list as collected-but-unscored. Line count is
    # only meaningful where wrapping is impossible, so the design side emits it for text
    # whose box grows with its content and stays silent otherwise (see `parse_op_facts` /
    # `_figma_node_facts`); an absent value is `not_applicable`, not a pass. ×1 and not
    # critical, so a source that cannot state it lowers `coverage` rather than forcing
    # INCONCLUSIVE — the same reasoning that puts `opacity` at ×1.
    _c("line_count", "line_count", _KIND_EXACT, 0.0, WEIGHT_STANDARD),
)

#: Categories that are checked only where a map entry opts in to them.
#:
#: A map that declares no asset digest for an element has not asked for the check
#: there, which is not the same as being blind to it — so the default state is
#: `not_applicable` and cannot escalate. Without this, every map would have to declare
#: a digest for every element and the escalation would become noise.
OPT_IN_CATEGORY_KEYS = frozenset({"asset"})

#: Categories whose unverifiability forces INCONCLUSIVE instead of PASS.
CRITICAL_CATEGORY_KEYS = frozenset(spec.key for spec in CATEGORIES if spec.critical)

#: Categories that only a text element can have.
#:
#: A frame has no font, so its typography rows are absent for a legitimate reason.
#: Treating that as "the design source withheld the property" made every realistic
#: run INCONCLUSIVE — a graphic frame cannot have a `font-weight`, and escalating
#: on it would permanently block the gate it is supposed to make usable. `line_count`
#: is here for the same reason: a frame has no lines to wrap.
TYPOGRAPHY_CATEGORY_KEYS = frozenset(
    {"font_size", "font_weight", "font_family", "line_height", "letter_spacing", "fg_color", "line_count"}
)

#: Categories **no reference side can state**, so no run can ever verify them.
#:
#: `margin` (#3) is the legacy spacing mechanism auto-layout replaced with `gap` (#14).
#: Neither design extractor has a code path for it — `pixel_sources` reads `itemSpacing`,
#: `layout.mode` and `borderRadius`, never a margin, because neither authoring tool models
#: one any more. The implementation side *does* measure it (`dom-facts-extractor.js` reads
#: all four computed sides), which is what makes this the opposite of a dead row: the
#: measurement exists, the counterpart does not, and the comparator can only report
#: `absent_from_design` for the rest of the gate's life.
#:
#: Left in `coverage` that cost every run in this gate's history one point of loss for a
#: comparison that was never on offer — the same mistake as reading an unproduced zero as a
#: withheld value (§4.1), one level up. Keeping it in §1 and in :data:`CATEGORIES` is
#: deliberate: every category is cited by its §1 number, one row per declared property
#: keeps that numbering stable, and the row documents a missing *reference-side* capability
#: rather than a missing check. It is excluded from the denominator and named in the report
#: so the exclusion is disclosed instead of silent.
#:
#: `tests/test_pixel.py` pins both halves — no design extractor emits it, and the DOM
#: extractor does — so implementing reference-side support fails the build here rather than
#: quietly keeping the exclusion.
UNREACHABLE_CATEGORY_KEYS = frozenset({"margin"})


# --- Colour maths (§1 #10/#11: ΔE 1976 CIE76) --------------------------------


def _srgb_to_linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


#: Colour functions whose arguments are space-separated with an optional
#: slash-delimited alpha. Chrome reports the result of `color-mix(in oklab, …)` —
#: what Tailwind v4 compiles an opacity modifier such as `text-white/90` into — as
#: `oklab(…)`, which the comma-oriented `rgb()` branch cannot read. A category the
#: parser drops is invisible: it neither passes nor fails, it just stops being
#: checked, so this is a silent hole rather than a loud one.
_MODERN_COLOR_PREFIXES = ("oklab(", "oklch(")


def _number(token: str) -> Optional[float]:
    """One numeric argument of a colour function, with or without a ``%``."""
    try:
        return float(token[:-1]) / 100.0 if token.endswith("%") else float(token)
    except ValueError:
        return None


def _linear_to_srgb(channel: float) -> float:
    if channel <= 0.0031308:
        return 12.92 * channel
    return 1.055 * (channel ** (1.0 / 2.4)) - 0.055


def _oklab_to_srgb(lightness: float, a: float, b: float) -> Tuple[float, float, float]:
    """OKLab -> gamma-encoded sRGB, clamped into the displayable cube.

    The matrices are Björn Ottosson's definition of the space. The clamp is
    deliberate: a colour outside the sRGB gamut has no exact hex equivalent, and
    leaving a channel negative or above 1 would hand the ΔE comparison a value no
    other colour in the pipeline can produce.
    """
    l_ = lightness + 0.3963377774 * a + 0.2158037573 * b
    m_ = lightness - 0.1055613458 * a - 0.0638541728 * b
    s_ = lightness - 0.0894841775 * a - 1.2914855480 * b
    # Long/medium/short cone response, cubed: OKLab's single non-linearity.
    lms = (l_**3, m_**3, s_**3)
    return (
        min(1.0, max(0.0, _linear_to_srgb(4.0767416621 * lms[0] - 3.3077115913 * lms[1] + 0.2309699292 * lms[2]))),
        min(1.0, max(0.0, _linear_to_srgb(-1.2684380046 * lms[0] + 2.6097574011 * lms[1] - 0.3413193965 * lms[2]))),
        min(1.0, max(0.0, _linear_to_srgb(-0.0041960863 * lms[0] - 0.7034186147 * lms[1] + 1.7076147010 * lms[2]))),
    )


def _parse_modern_color(text: str) -> Optional[Tuple[float, float, float, float]]:
    """``oklab(L a b[/ alpha])`` / ``oklch(L C H[/ alpha])`` -> sRGB RGBA 0..1."""
    inner = text[text.find("(") + 1 : text.rfind(")")]
    head, _, alpha_token = inner.partition("/")
    tokens = head.split()
    if len(tokens) != 3:
        return None

    values: List[float] = []
    for token in tokens:
        parsed = _number(token)
        if parsed is None:
            return None
        values.append(parsed)

    alpha = 1.0
    if alpha_token.strip():
        parsed_alpha = _number(alpha_token.strip())
        if parsed_alpha is None:
            return None
        alpha = parsed_alpha

    lightness, first, second = values
    if text.startswith("oklch"):
        radians = math.radians(second)
        a, b = first * math.cos(radians), first * math.sin(radians)
    else:
        a, b = first, second
    red, green, blue = _oklab_to_srgb(lightness, a, b)
    return (red, green, blue, min(1.0, max(0.0, alpha)))


def parse_color(value: Any) -> Optional[Tuple[float, float, float, float]]:
    """Parse a CSS colour into sRGB RGBA 0..1, or ``None`` when unparseable.

    Reads ``#rgb`` / ``#rrggbb`` / ``rgb()`` / ``rgba()`` / ``oklab()`` /
    ``oklch()``. Returns ``None`` for anything else — gradients, image fills,
    keywords — so the caller marks the category unverified rather than guessing.
    """
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if text.startswith("#"):
        digits = text[1:]
        if len(digits) == 3:
            digits = "".join(ch * 2 for ch in digits)
        if len(digits) not in (6, 8):
            return None
        try:
            parts = [int(digits[i : i + 2], 16) / 255.0 for i in range(0, len(digits), 2)]
        except ValueError:
            return None
        if len(parts) == 3:
            parts.append(1.0)
        return (parts[0], parts[1], parts[2], parts[3])
    if text.startswith(_MODERN_COLOR_PREFIXES):
        return _parse_modern_color(text)
    if text.startswith("rgb"):
        inner = text[text.find("(") + 1 : text.rfind(")")]
        chunks = [c.strip() for c in inner.split(",")]
        if len(chunks) < 3:
            return None
        try:
            rgb = [float(c.rstrip("%")) / (100.0 if c.endswith("%") else 255.0) for c in chunks[:3]]
            alpha = float(chunks[3]) if len(chunks) > 3 else 1.0
        except ValueError:
            return None
        return (rgb[0], rgb[1], rgb[2], alpha)
    return None


def _rgba_to_lab(rgba: Tuple[float, float, float, float]) -> Tuple[float, float, float]:
    r, g, b = (_srgb_to_linear(c) for c in rgba[:3])
    # sRGB -> XYZ (D65), then XYZ -> CIE Lab.
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = (0.2126729 * r + 0.7151522 * g + 0.0721750 * b) / 1.00000
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 0.008856 else (7.787 * t) + (16.0 / 116.0)

    fx, fy, fz = f(x), f(y), f(z)
    return ((116.0 * fy) - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def delta_e(color_a: Any, color_b: Any) -> Optional[float]:
    """CIE76 ΔE between two colours, or ``None`` when either is unparseable."""
    a, b = parse_color(color_a), parse_color(color_b)
    if a is None or b is None:
        return None
    la, lb = _rgba_to_lab(a), _rgba_to_lab(b)
    return sum((la[i] - lb[i]) ** 2 for i in range(3)) ** 0.5


# --- Paints: a flat colour, or a gradient (§6.1 "gradient and multi-fill") ----

#: Returned when two paints differ *structurally* — a gradient against a flat colour,
#: a different gradient kind, a different stop count, or an axis/stop position outside
#: tolerance. Expressed on the ΔE scale so it exceeds every colour tolerance and
#: clamps the row's unit score to 0 without inventing a pixel figure.
PAINT_MISMATCH = 100.0

#: Percentage points a gradient stop may move and still describe the same paint.
GRADIENT_POSITION_TOLERANCE = 2.0
#: Degrees the gradient axis may differ by, when both sides state one numerically.
GRADIENT_ANGLE_TOLERANCE = 2.0

_GRADIENT_RE = re.compile(r"^(?P<kind>[a-z-]+-gradient)\((?P<body>.*)\)$")
_ANGLE_RE = re.compile(r"(-?\d+(?:\.\d+)?)deg")
_STOP_RE = re.compile(r"^(?P<colour>.+?)\s+(?P<position>-?\d+(?:\.\d+)?)%$")


def _split_top_level(value: str) -> List[str]:
    """Split on commas that are not inside parentheses.

    A gradient's stops are comma-separated, but each stop's colour function carries
    its own commas (`rgba(98, 70, 229, 1)`), so a plain ``split(",")`` shreds them.
    """
    parts: List[str] = []
    depth = 0
    current: List[str] = []
    for char in value:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    parts.append("".join(current).strip())
    return [part for part in parts if part]


def _gradient_stop(raw: str) -> Tuple[str, Optional[float]]:
    """One gradient stop -> ``(colour, position%)``; the position is often omitted."""
    match = _STOP_RE.match(raw)
    if match and parse_color(match.group("colour")) is not None:
        return match.group("colour"), float(match.group("position"))
    return raw, None


def parse_gradient(value: Any) -> Optional[Dict[str, Any]]:
    """``linear-gradient(90deg, rgba(..) 0%, ..)`` -> ``{kind, angle, stops}``.

    Returns ``None`` for anything that is not a gradient, and for a gradient whose
    stops cannot be read — an unreadable definition is an absence, never a mismatch.
    """
    if not isinstance(value, str):
        return None
    match = _GRADIENT_RE.match(value.strip().lower())
    if not match:
        return None
    parts = _split_top_level(match.group("body"))
    if len(parts) < 2:
        return None

    # The first part is a stop when it reads as a colour, otherwise it is the prelude
    # (`90deg`, `to right`, `circle`, `from 114deg at 68% 42%`).
    angle: Optional[float] = None
    if parse_color(parts[0]) is None and parse_color(_gradient_stop(parts[0])[0]) is None:
        angle_match = _ANGLE_RE.search(parts[0])
        angle = float(angle_match.group(1)) if angle_match else None
        parts = parts[1:]

    stops = [_gradient_stop(part) for part in parts]
    if any(parse_color(colour) is None for colour, _ in stops):
        return None
    return {"kind": match.group("kind"), "angle": angle, "stops": stops}


def is_gradient(value: Any) -> bool:
    """Whether a paint is expressed as a gradient rather than one flat colour."""
    return isinstance(value, str) and _GRADIENT_RE.match(value.strip().lower()) is not None


def _gradient_deviation(design: str, actual: str) -> Optional[float]:
    left, right = parse_gradient(design), parse_gradient(actual)
    if left is None or right is None:
        return None
    if left["kind"] != right["kind"] or len(left["stops"]) != len(right["stops"]):
        return PAINT_MISMATCH
    left_angle, right_angle = left["angle"], right["angle"]
    if left_angle is not None and right_angle is not None:
        if abs(left_angle - right_angle) > GRADIENT_ANGLE_TOLERANCE:
            return PAINT_MISMATCH
    worst = 0.0
    for (left_colour, left_pos), (right_colour, right_pos) in zip(left["stops"], right["stops"]):
        stop = delta_e(left_colour, right_colour)
        if stop is None:
            return None
        worst = max(worst, stop)
        if left_pos is not None and right_pos is not None:
            if abs(left_pos - right_pos) > GRADIENT_POSITION_TOLERANCE:
                return PAINT_MISMATCH
    return worst


def _paint_deviation(design: Any, actual: Any) -> Optional[float]:
    """ΔE between two flat colours; a structural distance between two gradients.

    A flat colour against a gradient is not "unverifiable" — it is precisely the
    failure this category used to be blind to, and recording it as an absence is what
    let a gradient design pass against a solid implementation (§6.1).
    """
    design_is_gradient, actual_is_gradient = is_gradient(design), is_gradient(actual)
    if design_is_gradient or actual_is_gradient:
        if design_is_gradient != actual_is_gradient:
            return PAINT_MISMATCH
        return _gradient_deviation(design, actual)
    return delta_e(design, actual)


def _as_paint_stack(value: Any) -> Optional[List[str]]:
    """A paint stack as a bottom-to-top list of comparable paints, or ``None`` when absent.

    A single paint is accepted bare, the same tolerance `_as_list` extends to a bare number:
    a hand-written facts file that states one colour names a one-layer stack, and refusing it
    would reject a comparison the engine performs correctly. A list whose entries are not all
    strings is not a stack this comparator can layer — it returns ``None`` rather than
    comparing ``repr``s of objects nobody described.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)) and all(isinstance(entry, str) for entry in value):
        return list(value)
    return None


# --- Measurement ------------------------------------------------------------


@dataclass(frozen=True)
class Measurement:
    """One compared value: design says X, the DOM says Y, deviation D."""

    category: str
    element: str
    axis: str
    design: Any
    actual: Any
    tolerance: float
    weight: float
    deviation: Optional[float]
    verified: bool
    passed: bool

    def to_json(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "element": self.element,
            "axis": self.axis,
            "design": self.design,
            "actual": self.actual,
            "deviation": self.deviation,
            "tolerance": self.tolerance,
            "weight": self.weight,
            "verified": self.verified,
            "passed": self.passed,
        }


@dataclass
class Report:
    """The gate's verdict plus everything needed to act on it."""

    verdict: str
    score: Optional[float]
    within_tolerance_pct: Optional[float]
    max_critical_deviation_px: Optional[float]
    measurements: List[Measurement] = field(default_factory=list)
    skipped_categories: List[Dict[str, str]] = field(default_factory=list)
    elements: int = 0
    backend: str = ""
    reason: str = ""
    #: Fraction of the gate's **reachable** category surface that this run actually
    #: checked, i.e. `verified keys / (len(CATEGORIES) - len(UNREACHABLE_CATEGORY_KEYS))`.
    #: The denominator is the spec itself and therefore fixed, so the number is comparable
    #: across runs and across backends — which a row-level ratio is not, since normal
    #: inapplicability (a frame has no font) would swamp it.
    coverage: Optional[float] = None
    #: Category keys that no element verified. This is the complement of
    #: `coverage`, named so a PASS can disclose what it did not look at.
    unverified_categories: List[str] = field(default_factory=list)
    #: Category keys held out of the `coverage` denominator because no reference side
    #: can state them (`UNREACHABLE_CATEGORY_KEYS`). Distinct from
    #: `unverified_categories`: those are this run's gaps, these are permanent and no
    #: amount of work closes them. The report carries them so the exclusion is a
    #: disclosure rather than a silent discount — a reader can see the surface `coverage`
    #: is a fraction of, without having to know this module's constants.
    unreachable_categories: List[str] = field(default_factory=list)
    #: `ok` when both sides declared matching viewports, else `undeclared`. A
    #: MISMATCH never reaches the report: it is refused as a usage error, because
    #: it invalidates every measurement rather than one category.
    viewport_binding: str = ""
    design_viewport: Optional[int] = None
    dom_viewport: Optional[int] = None
    #: Which pass over this screen this report is. §5 allows two, and the runner
    #: refuses a third without a recorded override. A pixel gate is a
    #: measure → edit → measure loop whose only natural stop is a verdict, so the
    #: budget has to be enforced rather than trusted.
    attempt: int = 1
    #: Digests of the two inputs. A re-run whose digests changed is a **new
    #: baseline**, not a retry: the map or the design moved, so comparing this score
    #: against the previous one measures the edit to the goalposts, not the work.
    design_map_sha256: str = ""
    design_source_sha256: str = ""
    #: The user's verbatim acceptance, recorded only when it was required to exceed
    #: the attempt budget. Empty means no override was claimed.
    override_reason: str = ""

    @property
    def failures(self) -> List[Measurement]:
        """Verified measurements that missed tolerance, worst deviation first."""
        bad = [m for m in self.measurements if m.verified and not m.passed]
        return sorted(bad, key=lambda m: (-(m.deviation or 0.0), m.category))

    def to_json(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "score": self.score,
            "within_tolerance_pct": self.within_tolerance_pct,
            "max_critical_deviation_px": self.max_critical_deviation_px,
            "elements_compared": self.elements,
            "backend": self.backend,
            "reason": self.reason,
            "coverage": self.coverage,
            "unverified_categories": self.unverified_categories,
            "unreachable_categories": self.unreachable_categories,
            "viewport_binding": self.viewport_binding,
            "design_viewport": self.design_viewport,
            "dom_viewport": self.dom_viewport,
            "attempt": self.attempt,
            "design_map_sha256": self.design_map_sha256,
            "design_source_sha256": self.design_source_sha256,
            "override_reason": self.override_reason,
            "thresholds": {
                "pass_score_min": PASS_SCORE_MIN,
                "pass_within_tolerance_pct": PASS_WITHIN_TOLERANCE_PCT,
                "pass_critical_max_deviation_px": PASS_CRITICAL_MAX_DEVIATION_PX,
            },
            "skipped_categories": self.skipped_categories,
            "top_deviations": [m.to_json() for m in self.failures[:10]],
            "measurements": [m.to_json() for m in self.measurements],
        }


# --- Comparison -------------------------------------------------------------


def _as_list(value: Any, size: int) -> Optional[List[float]]:
    """Coerce a padding/radius/gap value to exactly ``size`` numbers.

    Accepts a number (broadcast), a CSS shorthand string (``"20px 40px"``) or a
    list, because the two design backends and the DOM disagree on the shape.

    An exact-length list is returned as-is *before* the 2-value shorthand rule, so
    the two-axis categories (`gap`) are not mangled into four numbers by a rule
    that only ever made sense for the four-sided ones.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return [float(value)] * size
    if isinstance(value, str):
        parts = [p for p in value.replace("px", " ").split() if p.strip()]
        try:
            nums = [float(p) for p in parts]
        except ValueError:
            return None
    elif isinstance(value, (list, tuple)):
        try:
            nums = [float(v) for v in value]
        except (TypeError, ValueError):
            return None
    else:
        return None

    if not nums:
        return None
    if len(nums) == size:
        return nums
    if len(nums) == 1:
        return nums * size
    if len(nums) == 2:
        # CSS shorthand: vertical horizontal.
        return [nums[0], nums[1], nums[0], nums[1]]
    return None


def _first_family(stack: Any) -> str:
    """The first family of a CSS font stack, normalised for comparison.

    A design states a single family while the browser reports the whole resolved
    stack (`Volkhov, "Volkhov Fallback", serif`), so comparing the raw strings
    would fail every text node. Quotes, case and surrounding space are all
    presentational; an empty result means "no family to compare", not "different".
    """
    if not isinstance(stack, str):
        return ""
    return stack.split(",")[0].strip().strip("'").strip('"').lower()


def _deviation(spec: CategorySpec, design: Any, actual: Any) -> Optional[float]:
    if spec.kind in (_KIND_PX, _KIND_PX_LIST, _KIND_PX_VEC):
        try:
            return abs(float(design) - float(actual))
        except (TypeError, ValueError):
            return None
    if spec.kind in (_KIND_COLOR, _KIND_PAINT_STACK):
        # A stack reaches here one layer at a time, so the unit of comparison is the same
        # paint the single-valued colour category compares.
        return _paint_deviation(design, actual)
    if spec.kind in (_KIND_RATIO, _KIND_EM, _KIND_SCALAR):
        try:
            return abs(float(design) - float(actual))
        except (TypeError, ValueError):
            return None
    return None


def _shadow_axes(design: Any, actual: Any) -> Optional[List[Tuple[str, float, float]]]:
    """Compare a single shadow; a missing shadow on either side is a deviation."""
    if not design and not actual:
        return []
    if not design or not actual:
        return [(axis, 0.0, float("inf")) for axis in ("x", "y", "blur", "spread", "alpha")]
    out: List[Tuple[str, float, float]] = []
    for axis in ("x", "y", "blur", "spread", "alpha"):
        try:
            out.append((axis, float(design.get(axis, 0.0)), float(actual.get(axis, 0.0))))
        except (AttributeError, TypeError, ValueError):
            return None
    return out


_SHADOW_TOLERANCE = {"x": 2.0, "y": 2.0, "blur": 4.0, "spread": 4.0, "alpha": 0.04}


def _is_text(design: Dict[str, Any]) -> bool:
    """Whether typography applies to this element.

    Both extractors annotate their facts with the design node's `kind`. When the
    kind is unknown — a hand-written facts file, or a future backend — the answer
    is "yes, typography applies", so a missing font stays a real gap. Guessing
    "not applicable" would silently excuse an unmeasured ×2 category.
    """
    kind = design.get("kind")
    if isinstance(kind, str) and kind:
        return kind.lower() == "text"
    return True


def _frame_problem(design: Dict[str, Any], actual: Dict[str, Any]) -> Optional[str]:
    """Why `position` cannot be compared, or ``None`` when it can.

    Coordinates only mean something inside a declared frame. The design side is
    parent-relative (`locationRelativeToParent`) while the DOM side reports
    `getBoundingClientRect()`, which is viewport-relative — so differencing the two
    does not measure layout drift, it measures the distance between two unrelated
    origins and reports it with a confident-looking number. That is a false FAIL
    (and, on a coincidence, a false PASS), so the positions are not compared at all.

    An undeclared frame is incomparable for the same reason: a comparison that
    cannot be shown to be meaningful is not one.
    """
    design_frame = design.get("coord_frame")
    actual_frame = actual.get("coord_frame")
    if design_frame == COORD_FRAME_NONE:
        return "coord_frame_absent"
    if not design_frame or not actual_frame:
        return "coord_frame_undeclared"
    if design_frame != actual_frame:
        return "coord_frame_mismatch"
    return None


def compare_element(
    key: str,
    design: Dict[str, Any],
    actual: Dict[str, Any],
) -> Tuple[List[Measurement], List[Dict[str, str]]]:
    """Compare one element's design facts against its DOM facts.

    Returns ``(measurements, skipped)``. A measurement whose design value is
    absent is emitted once as verified=False so the caller can report it.
    """
    measurements: List[Measurement] = []
    skipped: List[Dict[str, str]] = []

    def emit(spec: CategorySpec, axis: str, design_value: Any, actual_value: Any, tol: float) -> None:
        deviation = _deviation(spec, design_value, actual_value)
        if deviation is None:
            measurements.append(
                Measurement(spec.key, key, axis, design_value, actual_value, tol, spec.weight, None, False, False)
            )
            skipped.append({"category": spec.key, "element": key, "axis": axis, "reason": "not_comparable"})
            return
        measurements.append(
            Measurement(
                spec.key,
                key,
                axis,
                design_value,
                actual_value,
                tol,
                spec.weight,
                deviation,
                True,
                deviation <= tol,
            )
        )

    for spec in CATEGORIES:
        if spec.key in ("box", "position"):
            origin_design = design.get(spec.prop) or {}
            origin_actual = actual.get(spec.prop) or {}
            # None for `box` — width/height are frame-independent, only origin is not.
            frame_problem = _frame_problem(design, actual) if spec.key == "position" else None
            for axis in spec.axes:
                actual_value = origin_actual.get(axis)
                if axis not in origin_design:
                    measurements.append(
                        Measurement(
                            spec.key,
                            key,
                            axis,
                            None,
                            actual_value,
                            spec.tolerance,
                            spec.weight,
                            None,
                            False,
                            False,
                        )
                    )
                    skipped.append({"category": spec.key, "element": key, "axis": axis, "reason": "absent_from_design"})
                    continue
                if frame_problem is not None:
                    measurements.append(
                        Measurement(
                            spec.key,
                            key,
                            axis,
                            origin_design[axis],
                            actual_value,
                            spec.tolerance,
                            spec.weight,
                            None,
                            False,
                            False,
                        )
                    )
                    skipped.append({"category": spec.key, "element": key, "axis": axis, "reason": frame_problem})
                    continue
                emit(spec, axis, origin_design[axis], actual_value, spec.tolerance)
            continue

        if spec.kind == _KIND_PX_LIST:
            design_values = _as_list(design.get(spec.prop), len(spec.axes))
            actual_values = _as_list(actual.get(spec.prop), len(spec.axes))
            if design_values is None:
                for axis in spec.axes:
                    measurements.append(
                        Measurement(spec.key, key, axis, None, None, spec.tolerance, spec.weight, None, False, False)
                    )
                    skipped.append({"category": spec.key, "element": key, "axis": axis, "reason": "absent_from_design"})
                continue
            for i, axis in enumerate(spec.axes):
                emit(
                    spec,
                    axis,
                    design_values[i],
                    (actual_values or [None] * len(spec.axes))[i],
                    spec.tolerance,
                )
            continue

        if spec.kind == _KIND_SHADOW:
            design_shadow = design.get(spec.prop) or {}
            actual_shadow = actual.get(spec.prop) or {}
            if not design_shadow:
                for axis in spec.axes:
                    measurements.append(
                        Measurement(spec.key, key, axis, None, None, spec.tolerance, spec.weight, None, False, False)
                    )
                    skipped.append({"category": spec.key, "element": key, "axis": axis, "reason": "absent_from_design"})
                continue
            pairs = _shadow_axes(design_shadow, actual_shadow)
            if pairs is None:
                measurements.append(
                    Measurement(
                        spec.key, key, "", design_shadow, actual_shadow, spec.tolerance, spec.weight, None, False, False
                    )
                )
                skipped.append({"category": spec.key, "element": key, "axis": "", "reason": "not_comparable"})
                continue
            for axis, dval, aval in pairs:
                tol = _SHADOW_TOLERANCE[axis]
                measurements.append(
                    Measurement(
                        spec.key,
                        key,
                        axis,
                        dval,
                        aval,
                        tol,
                        spec.weight,
                        abs(dval - aval),
                        True,
                        abs(dval - aval) <= tol,
                    )
                )
            continue

        if spec.kind == _KIND_PAINT_STACK:
            design_stack = _as_paint_stack(design.get(spec.prop))
            actual_stack = _as_paint_stack(actual.get(spec.prop))
            if design_stack is None:
                measurements.append(
                    Measurement(spec.key, key, "", None, actual_stack, spec.tolerance, spec.weight, None, False, False)
                )
                skipped.append({"category": spec.key, "element": key, "axis": "", "reason": "absent_from_design"})
                continue
            # Layer by layer, so a deviation names the layer that is wrong rather than the whole
            # background. A stack whose length differs is itself the finding — an implementation
            # that dropped a paint is missing a layer, not drifting inside one — and it is
            # reported on the layer that has no counterpart, where a reviewer can see which one
            # went missing. `PAINT_MISMATCH` rather than an absence, because the two sides
            # disagree about what exists, which is not "unverifiable".
            for index in range(max(len(design_stack), len(actual_stack or ()))):
                axis = f"layer[{index}]"
                left = design_stack[index] if index < len(design_stack) else None
                right = actual_stack[index] if actual_stack is not None and index < len(actual_stack) else None
                if left is None or right is None:
                    measurements.append(
                        Measurement(
                            spec.key, key, axis, left, right, spec.tolerance, spec.weight, PAINT_MISMATCH, True, False
                        )
                    )
                    continue
                emit(spec, axis, left, right, spec.tolerance)
            continue

        if spec.prop not in design:
            measurements.append(
                Measurement(
                    spec.key, key, "", None, actual.get(spec.prop), spec.tolerance, spec.weight, None, False, False
                )
            )
            skipped.append({"category": spec.key, "element": key, "axis": "", "reason": "absent_from_design"})
            continue

        if spec.kind in (_KIND_EXACT, _KIND_FAMILY):
            design_value = design[spec.prop]
            actual_value = actual.get(spec.prop)
            if spec.kind == _KIND_FAMILY:
                # Compared — and reported — as the normalised first family, so a
                # mismatch reads as "poppins vs volkhov" rather than as two long
                # fallback stacks.
                design_value, actual_value = _first_family(design_value), _first_family(actual_value)
            # A value the implementation side never supplied is an *absence*, not a
            # mismatch: nothing was measured, so nothing may be convicted. Without this
            # a missing `font_weight` compared unequal to every number and reported a
            # confident FAIL — the same "confident wrong number" that the position guard
            # and the implicit-zero rules exist to prevent.
            if design_value is None or actual_value is None or actual_value == "":
                measurements.append(
                    Measurement(spec.key, key, "", None, None, spec.tolerance, spec.weight, None, False, False)
                )
                skipped.append({"category": spec.key, "element": key, "axis": "", "reason": "not_comparable"})
                continue
            deviation = 0.0 if design_value == actual_value else 1.0
            measurements.append(
                Measurement(
                    spec.key,
                    key,
                    "",
                    design_value,
                    actual_value,
                    spec.tolerance,
                    spec.weight,
                    deviation,
                    True,
                    deviation == 0.0,
                )
            )
            continue

        emit(spec, "", design[spec.prop], actual.get(spec.prop), spec.tolerance)

    # Reclassify typography absences on a non-text element. Done here, once, rather
    # than at each of the absent-value branches above: the rule is about the
    # element, not about which category shape happened to detect the absence.
    if not _is_text(design):
        for entry in skipped:
            if entry["reason"] == "absent_from_design" and entry["category"] in TYPOGRAPHY_CATEGORY_KEYS:
                entry["reason"] = "not_applicable"

    # Same idea for the opt-in categories: their default state is "not asked for".
    for entry in skipped:
        if entry["reason"] == "absent_from_design" and entry["category"] in OPT_IN_CATEGORY_KEYS:
            entry["reason"] = "not_applicable"

    return measurements, skipped


def _unit_score(measurement: Measurement) -> float:
    """Fraction of a measurement's tolerance budget left unused, clamped to [0, 1].

    A zero-tolerance category (`_KIND_EXACT`, e.g. ``font_weight``) is all or
    nothing — an exact match is a perfect 1.0, a mismatch a hard 0.0. The ratio
    form would divide by zero, so it is handled before the general case.
    """
    if measurement.tolerance <= 0:
        return 1.0 if measurement.passed else 0.0
    return max(0.0, 1.0 - (measurement.deviation or 0.0) / measurement.tolerance)


def _coverage(measurements: List[Measurement]) -> Tuple[float, List[str]]:
    """How much of the gate's **reachable** category surface this run actually checked.

    The denominator is :data:`CATEGORIES` minus :data:`UNREACHABLE_CATEGORY_KEYS` — the spec
    itself, not the number of measurement rows, so the figure stays comparable across runs
    and across backends. A row-level ratio would be swamped by normal inapplicability (a
    frame has no font, most text nodes have no explicit padding row) and would report roughly
    the same number for a thorough run and a nearly blind one.

    Excluding the unreachable categories is what makes the number mean "of what could have
    been measured, how much was": keeping them charged a constant loss no run could ever
    recover, so a perfect run and a nearly perfect one differed by less than the dead weight
    they both carried.

    Returns ``(fraction, unverified_category_keys)``; the second element is the complement
    of the first over the reachable surface, in spec order, so it can only ever name
    categories this gate actually declares.
    """
    reachable = [spec.key for spec in CATEGORIES if spec.key not in UNREACHABLE_CATEGORY_KEYS]
    verified = {m.category for m in measurements if m.verified}
    checked = [key for key in reachable if key in verified]
    return round(len(checked) / len(reachable), 4), [key for key in reachable if key not in verified]


def _is_wholly_inapplicable(category: str, skipped: List[Dict[str, str]]) -> bool:
    """Whether `not_applicable` alone explains every skip of one category.

    The one legitimate reason for a critical category to go unmeasured across a whole
    run: nothing that was mapped can carry it. A frame has no font, so a frame-only
    screen is not *blind* to typography — it has nothing on which to measure it, and
    escalating there would block the gate it exists to make usable.
    """
    reasons = {entry["reason"] for entry in skipped if entry["category"] == category}
    return bool(reasons) and reasons == {"not_applicable"}


def build_report(
    design_elements: Dict[str, Dict[str, Any]],
    dom_elements: Dict[str, Dict[str, Any]],
    *,
    backend: str = "",
) -> Report:
    """Score every element present on both sides and apply the gate's PASS rules.

    Preconditions: both maps are keyed by the same element keys (the caller has
    already applied `design-map.json`). Elements present on only one side are
    reported as skipped rather than silently ignored.
    """
    measurements: List[Measurement] = []
    skipped: List[Dict[str, str]] = []

    for key in sorted(set(design_elements) | set(dom_elements)):
        design = design_elements.get(key)
        actual = dom_elements.get(key)
        if design is None or actual is None:
            missing = "design" if design is None else "dom"
            skipped.append({"category": "*", "element": key, "axis": "", "reason": f"missing_from_{missing}"})
            continue
        element_measurements, element_skipped = compare_element(key, design, actual)
        measurements.extend(element_measurements)
        skipped.extend(element_skipped)

    verified = [m for m in measurements if m.verified]
    coverage, unverified_categories = _coverage(measurements)
    unreachable_categories = sorted(UNREACHABLE_CATEGORY_KEYS)
    if not verified:
        return Report(
            verdict=VERDICT_INCONCLUSIVE,
            score=None,
            within_tolerance_pct=None,
            max_critical_deviation_px=None,
            measurements=measurements,
            skipped_categories=skipped,
            elements=len(design_elements),
            backend=backend,
            reason="no measurable property: the design source exposed nothing comparable",
            coverage=coverage,
            unverified_categories=unverified_categories,
            unreachable_categories=unreachable_categories,
        )

    total_weight = sum(m.weight for m in verified)
    weighted = sum(_unit_score(m) * m.weight for m in verified)
    score = round((weighted / total_weight) * 10.0, 1) if total_weight else 0.0

    passed = sum(1 for m in verified if m.passed)
    within = round(passed / len(verified), 4)

    #: Condition 3 covers every ×2 category that reports a deviation, not only the
    #: px-tolerance ones. `fg_color` carries a ΔE tolerance rather than a pixel
    #: budget, so it is absent from `critical_categorical_misses` below — that set
    #: is the rows carrying *no* tolerance — which makes this budget its only
    #: escalation. Filtering it down to `padding` and `font_size` therefore removed
    #: the gate's only way to fail a wrong foreground on a critical element.
    critical_deviations = [m.deviation or 0.0 for m in verified if m.weight == WEIGHT_CRITICAL]
    max_critical = round(max(critical_deviations), 2) if critical_deviations else 0.0

    #: §3 condition 3 is written as an 8px budget, which only describes the px
    #: categories. A category with no tolerance is wrong or it is not — there is no
    #: such thing as "3px of the wrong typeface" — and its deviation is a flag (1.0),
    #: so it could never exceed 8 and never tripped the condition. A single
    #: mismatched ×2 category cost 2 of ~41 weight and left the score at 9.5, inside
    #: every numeric condition: the run passed while rendering the wrong font.
    critical_categorical_misses = sorted(
        {m.category for m in verified if m.weight == WEIGHT_CRITICAL and m.tolerance <= 0 and not m.passed}
    )

    # A critical category escalates only when the run measured it on NO element and
    # inapplicability does not explain that. Which *side* failed to supply the value
    # is deliberately not part of the test: the design source withholding `padding`
    # and the caller never collecting `font-family` from the DOM leave the gate equally
    # blind, so keying on `absent_from_design` alone made "do not measure it" a way to
    # opt out of the escalation. Per-element absence stays normal — a text node has no
    # explicit padding row, a frame has no font — which is why the *reason set* for a
    # category, and not the count of skips, is what decides.
    unverified_critical = sorted(
        category
        for category in unverified_categories
        if category in CRITICAL_CATEGORY_KEYS and not _is_wholly_inapplicable(category, skipped)
    )

    report = Report(
        verdict=VERDICT_FAIL,
        score=score,
        within_tolerance_pct=within,
        max_critical_deviation_px=max_critical,
        measurements=measurements,
        skipped_categories=skipped,
        elements=len([k for k in design_elements if k in dom_elements]),
        backend=backend,
        coverage=coverage,
        unverified_categories=unverified_categories,
        unreachable_categories=unreachable_categories,
    )

    missing_from_dom = sorted({s["element"] for s in skipped if s["reason"] == "missing_from_dom"})
    if missing_from_dom:
        # The design declares an element the page does not render. It contributes no
        # measurement, so it cannot drag the score down — without this rule it would
        # sail through every numeric condition and the run would report PASS while
        # missing a component the designer specified.
        report.verdict = VERDICT_FAIL
        report.reason = "element(s) present in the design but absent from the DOM: " + ", ".join(missing_from_dom)
        return report

    missing_from_design = sorted({s["element"] for s in skipped if s["reason"] == "missing_from_design"})
    if missing_from_design:
        # Nothing at all was verified for these: the reference could not be read, so
        # neither PASS nor FAIL is earned. Usually a stale node id or the wrong
        # `--design-backend`, and worth surfacing loudly rather than scoring around.
        report.verdict = VERDICT_INCONCLUSIVE
        report.reason = "element(s) declared in design-map.json but absent from the design source: " + ", ".join(
            missing_from_design
        )
        return report

    if unverified_critical:
        # A critical property was never measured. PASS here would claim a
        # verification that did not happen, so the honest verdict is INCONCLUSIVE.
        report.verdict = VERDICT_INCONCLUSIVE
        report.reason = "critical property not measurable on any mapped element: " + ", ".join(unverified_critical)
        return report

    if (
        score >= PASS_SCORE_MIN
        and within >= PASS_WITHIN_TOLERANCE_PCT
        and max_critical <= PASS_CRITICAL_MAX_DEVIATION_PX
        and not critical_categorical_misses
    ):
        report.verdict = VERDICT_PASS
        return report

    reasons = []
    if score < PASS_SCORE_MIN:
        reasons.append(f"score {score} < {PASS_SCORE_MIN}")
    if within < PASS_WITHIN_TOLERANCE_PCT:
        reasons.append(f"within-tolerance {within} < {PASS_WITHIN_TOLERANCE_PCT}")
    if max_critical > PASS_CRITICAL_MAX_DEVIATION_PX:
        reasons.append(f"critical deviation {max_critical}px > {PASS_CRITICAL_MAX_DEVIATION_PX}px")
    if critical_categorical_misses:
        reasons.append("critical mismatch (category carries no tolerance): " + ", ".join(critical_categorical_misses))
    report.reason = "; ".join(reasons)
    return report


def remediation_steps(report: Report, limit: int = 3) -> List[str]:
    """The gate's retry policy: fix the top deviations, worst first."""
    return [
        f"{m.element}.{m.category}"
        + (f"[{m.axis}]" if m.axis else "")
        + f": design {m.design} vs actual {m.actual} (off by {round(m.deviation or 0.0, 2)})"
        for m in report.failures[:limit]
    ]


def summarise(report: Report) -> str:
    """One-line verdict for the decision log (`log_format_decisions`)."""
    score = "n/a" if report.score is None else report.score
    within = "n/a" if report.within_tolerance_pct is None else report.within_tolerance_pct
    worst = "n/a" if report.max_critical_deviation_px is None else report.max_critical_deviation_px
    coverage = "n/a" if report.coverage is None else report.coverage
    line = (
        f"[DOMAIN-GATE-EXECUTED] domain=ux gate=pixel-check-gate status={report.verdict} "
        f"score={score} within_4px_pct={within} deviation_max_px={worst} "
        f"elements={report.elements} coverage={coverage} attempt={report.attempt} "
        f"viewport={report.viewport_binding or 'n/a'} backend={report.backend or 'n/a'}"
    )
    # An override is the one field a reader must not miss: it means the budget or
    # the threshold was set aside by a human, so the line says so instead of
    # looking like every other run.
    if report.override_reason:
        line += f' override="{report.override_reason}"'
    # Named, not just counted: a PASS must be quotable together with the parts of the
    # gate it did not reach, otherwise "PASS" reads as "everything was checked".
    if report.unverified_categories:
        line += f" unverified={','.join(report.unverified_categories)}"
    # And the surface coverage is *not* a fraction of, for the same reason: without it a
    # reader sees a ceiling below 1.0 and cannot tell a fixed limit from work not done.
    if report.unreachable_categories:
        line += f" unreachable={','.join(report.unreachable_categories)}"
    return line


# --- Gate runner (the join §3.3 exists for) ---------------------------------


def resolve_design_source(source: Path, backend: str, node_ids: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    """Extract per-node facts from a raw design artefact.

    `source` is a `get_figma_data` response for `figma`, or a `.op` document for
    `openpencil`. The backend is never inferred from the file's shape: guessing
    would silently pick the wrong extractor and produce plausible-but-wrong
    numbers, and §3's backend contract is fail-closed for the same reason.

    A backend the UX domain declares but nothing here can read (`penpot`, see
    :data:`che_core.pixel_sources.BACKENDS_WITHOUT_EXTRACTOR`) is refused with its own
    message. The gate documents Penpot as a first-class alternative to Figma, so
    "unknown backend" would be a lie about the caller's request and would set them
    hunting a spelling error that does not exist.
    """
    if backend == "figma":
        return parse_figma_facts(Path(source).read_text(encoding="utf-8"), node_ids)
    if backend == "openpencil":
        return parse_op_facts(Path(source), node_ids)
    if backend in BACKENDS_WITHOUT_EXTRACTOR:
        raise ValueError(
            f"design backend {backend!r} is declared by the UX domain but has no extractor: "
            f"{sorted(BACKENDS_WITH_EXTRACTOR)} are implemented. Penpot's MCP server exposes "
            "`execute_code` rather than a fact-export tool, so its fact bag has to be recorded "
            "from a real session and pinned by a fixture first — see "
            "domains/ux/connectors/penpot.config.md, 'Wiring status'."
        )
    raise ValueError(
        f"unknown design backend {backend!r}: expected one of {sorted(BACKENDS_WITH_EXTRACTOR | BACKENDS_WITHOUT_EXTRACTOR)}"
    )


def join_by_map(
    design_map: Dict[str, Any],
    design_facts: Dict[str, Any],
    dom_facts: Dict[str, Any],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Re-key both sides by element key, using the map as the only join.

    Design nodes and DOM elements cannot be matched by inference (§3.3), so the
    map is the sole source of truth: `{element_key: {design_node, selector}}`, plus an
    optional `asset_sha256` that opts that element into §1 #17.

    An element is placed in a side's dict **only if that side has facts for it**.
    Emitting an empty bag instead would send `build_report` down the per-category
    path and report every category as `absent_from_design`, when the truth is
    that the element is missing from the DOM entirely — a different, and more
    actionable, diagnosis.
    """
    design_out: Dict[str, Dict[str, Any]] = {}
    dom_out: Dict[str, Dict[str, Any]] = {}

    for element, entry in design_map.items():
        if not isinstance(entry, dict) or not entry.get("design_node") or not entry.get("selector"):
            raise ValueError(
                f"design-map entry {element!r} must declare both `design_node` and `selector` "
                "(§3.3); without them the two sides cannot be joined"
            )
        node = entry["design_node"]
        selector = entry["selector"]
        if node in design_facts:
            facts = dict(design_facts[node])
            # The expected asset identity is declared here rather than extracted: the
            # design source carries an opaque vendor reference (`imageRef`), not the
            # digest of the bytes that will be served, so the human who freezes the map
            # is the only one who can state it (§6.1 "asset identity").
            digest = entry.get("asset_sha256")
            if digest is not None:
                if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                    raise ValueError(
                        f"design-map entry {element!r} declares an unusable `asset_sha256`: "
                        "expected 64 lowercase hex characters"
                    )
                facts["asset_sha256"] = digest
            design_out[element] = facts
        if selector in dom_facts:
            dom_out[element] = dom_facts[selector]

    return design_out, dom_out


def design_facts_record(
    design_map: Dict[str, Any],
    design_facts: Dict[str, Any],
    breakpoint: str = "",
) -> Dict[str, Any]:
    """The reference side in the shape §4.1 commits — one entry per mapped element.

    The vocabulary is deliberately the **flat** one the engine consumes, not a second
    nested presentation of the same numbers (`w`/`h`, `border: {width, color}`,
    `font: {size, …}`). A projector would be a second schema kept in sync by hand, and
    the file a reviewer checks could then disagree with the values that were scored —
    which is the exact failure §4.1's "text and git-diffable" requirement exists to
    prevent, one step removed.

    `breakpoint` is a scalar because the file is one per breakpoint (§2.4): a map of
    breakpoints would advertise a shape the resolver never produces.

    An element whose node the extractor could not read gets an empty `facts` object
    rather than being dropped. A missing entry would be indistinguishable from "this
    element was never mapped", and that distinction is the whole point of §2.6.
    """
    record: Dict[str, Any] = {}
    for element, entry in design_map.items():
        if not isinstance(entry, dict):
            continue
        node = entry.get("design_node")
        facts = dict(design_facts[node]) if isinstance(design_facts.get(node), dict) else {}
        # `asset_sha256` is declared on the map rather than extracted (§4.3), but it is
        # compared — so echoing it here is what makes the record equal to the facts the
        # engine scored, with no key the reader has to go and find elsewhere.
        if "asset_sha256" in entry:
            facts["asset_sha256"] = entry["asset_sha256"]
        record[element] = {
            "design_node": node,
            "selector": entry.get("selector", ""),
            "breakpoint": breakpoint or "undeclared",
            "facts": facts,
        }
    return record


def exit_code(report: Report) -> int:
    """Process exit status for the runner.

    INCONCLUSIVE deliberately does not share 0 with PASS: a caller that only
    checks the exit code must never read "could not verify" as "verified".
    """
    return _EXIT_CODES.get(report.verdict, 1)


#: §5's retry budget: one measurement plus one free retry. A third pass is not a
#: retry — it is either a new baseline (the digests changed) or an override, and
#: both are decisions a human makes, so the runner will not take one silently.
MAX_ATTEMPTS = 2


def run_check(
    design_map: Dict[str, Any],
    design_facts: Dict[str, Any],
    dom_facts: Dict[str, Any],
    *,
    backend: str = "",
    breakpoint: str = "",
    design_viewport: Optional[int] = None,
    dom_viewport: Optional[int] = None,
    attempt: int = 1,
    override_reason: str = "",
    design_map_sha256: str = "",
    design_source_sha256: str = "",
) -> Report:
    """Run the gate end to end: join both sides and apply §1/§2's rules.

    `design_facts` is keyed by design node id, `dom_facts` by CSS selector; both are the
    flat per-node form the extractors emit. §4.1's committed record is that same flat
    vocabulary re-keyed by element (`design_facts_record`), so the file a reviewer reads is
    built from these numbers rather than transcribed beside them. `breakpoint` is carried
    into the report as provenance only.

    The viewports are a precondition, not provenance. A design captured at 375px
    compared against a DOM measured at 1440px is not a nearly-passing run — every
    number it produces is meaningless, so that is refused here rather than scored
    and reported with a reassuring score next to it.

    The attempt number is the other precondition, for the same reason one step
    removed: without a budget the loop has no stop other than a verdict, and an
    INCONCLUSIVE verdict never supplies one. Exceeding the budget is refused rather
    than scored, and the only way past it is a recorded human override.
    """
    if attempt > MAX_ATTEMPTS and not override_reason.strip():
        raise ValueError(
            f"attempt {attempt} exceeds the retry budget of {MAX_ATTEMPTS} (§5): a third pass is not a "
            "retry. Pass --override-reason with the user's verbatim acceptance to proceed, or stop and "
            "resolve the failing verdict instead of re-running it"
        )
    if design_viewport is not None and dom_viewport is not None and design_viewport != dom_viewport:
        raise ValueError(
            f"viewport mismatch: the design was captured at {design_viewport}px and the DOM was measured "
            f"at {dom_viewport}px — no measurement between them is meaningful"
        )

    design_elements, dom_elements = join_by_map(design_map, design_facts, dom_facts)
    report = build_report(design_elements, dom_elements, backend=backend)
    if breakpoint:
        report.reason = f"[{breakpoint}] {report.reason}".strip()
    report.design_viewport = design_viewport
    report.dom_viewport = dom_viewport
    report.viewport_binding = "ok" if design_viewport is not None and design_viewport == dom_viewport else "undeclared"
    report.attempt = attempt
    report.override_reason = override_reason
    report.design_map_sha256 = design_map_sha256
    report.design_source_sha256 = design_source_sha256
    return report


def iter_categories() -> Iterable[CategorySpec]:
    return CATEGORIES
