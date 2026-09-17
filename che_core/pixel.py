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

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from che_core.pixel_sources import COORD_FRAME_NONE, parse_figma_facts, parse_op_facts

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
_KIND_RATIO = "ratio"
_KIND_EM = "em"
_KIND_PX_LIST = "px_list"
_KIND_PX_VEC = "px_vec"
_KIND_SHADOW = "shadow"


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
    _c("bg_color", "bg", _KIND_COLOR, MAX_DELTA_E, WEIGHT_STANDARD),
    _c("shadow", "shadow", _KIND_SHADOW, 2.0, WEIGHT_STANDARD, "x", "y", "blur", "spread", "alpha"),
    _c("position", "box_origin", _KIND_PX_VEC, 8.0, WEIGHT_MEDIUM, "x", "y"),
)

#: Categories whose unverifiability forces INCONCLUSIVE instead of PASS.
CRITICAL_CATEGORY_KEYS = frozenset(spec.key for spec in CATEGORIES if spec.critical)

#: Categories that only a text element can have.
#:
#: A frame has no font, so its typography rows are absent for a legitimate reason.
#: Treating that as "the design source withheld the property" made every realistic
#: run INCONCLUSIVE — a graphic frame cannot have a `font-weight`, and escalating
#: on it would permanently block the gate it is supposed to make usable.
TYPOGRAPHY_CATEGORY_KEYS = frozenset({"font_size", "font_weight", "line_height", "letter_spacing", "fg_color"})


# --- Colour maths (§1 #10/#11: ΔE 1976 CIE76) --------------------------------


def _srgb_to_linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def parse_color(value: Any) -> Optional[Tuple[float, float, float, float]]:
    """Parse ``#rgb`` / ``#rrggbb`` / ``rgb()`` / ``rgba()`` into linear-free RGBA 0..1.

    Returns ``None`` for anything unparseable (gradients, image fills, keywords)
    so the caller can mark the category unverified rather than guess a colour.
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
    #: Fraction of the gate's own category surface that this run actually checked,
    #: i.e. `verified category keys / len(CATEGORIES)`. The denominator is the
    #: spec itself and therefore fixed, so the number is comparable across runs
    #: and across backends — which a row-level ratio is not, since normal
    #: inapplicability (a frame has no font) would swamp it.
    coverage: Optional[float] = None
    #: Category keys that no element verified. This is the complement of
    #: `coverage`, named so a PASS can disclose what it did not look at.
    unverified_categories: List[str] = field(default_factory=list)
    #: `ok` when both sides declared matching viewports, else `undeclared`. A
    #: MISMATCH never reaches the report: it is refused as a usage error, because
    #: it invalidates every measurement rather than one category.
    viewport_binding: str = ""
    design_viewport: Optional[int] = None
    dom_viewport: Optional[int] = None

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
            "viewport_binding": self.viewport_binding,
            "design_viewport": self.design_viewport,
            "dom_viewport": self.dom_viewport,
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
    """Coerce a padding/radius value to exactly ``size`` numbers.

    Accepts a number (broadcast), a CSS shorthand string (``"20px 40px"``) or a
    list, because the two design backends and the DOM disagree on the shape.
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
    if len(nums) == 1:
        return nums * size
    if len(nums) == 2:
        # CSS shorthand: vertical horizontal.
        return [nums[0], nums[1], nums[0], nums[1]]
    if len(nums) == size:
        return nums
    return None


def _deviation(spec: CategorySpec, design: Any, actual: Any) -> Optional[float]:
    if spec.kind in (_KIND_PX, _KIND_PX_LIST, _KIND_PX_VEC):
        try:
            return abs(float(design) - float(actual))
        except (TypeError, ValueError):
            return None
    if spec.kind == _KIND_COLOR:
        return delta_e(design, actual)
    if spec.kind in (_KIND_RATIO, _KIND_EM):
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

        if spec.prop not in design:
            measurements.append(
                Measurement(
                    spec.key, key, "", None, actual.get(spec.prop), spec.tolerance, spec.weight, None, False, False
                )
            )
            skipped.append({"category": spec.key, "element": key, "axis": "", "reason": "absent_from_design"})
            continue

        if spec.kind == _KIND_EXACT:
            design_value = design[spec.prop]
            actual_value = actual.get(spec.prop)
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
    """How much of the gate's own category surface this run actually checked.

    The denominator is :data:`CATEGORIES` — the spec itself — and not the number of
    measurement rows, so the figure is comparable across runs and across backends.
    A row-level ratio would be swamped by normal inapplicability (a frame has no
    font, most text nodes have no explicit padding row), and would end up reporting
    roughly the same number for a thorough run and a nearly blind one.

    Returns ``(fraction, unverified_category_keys)``; the second element is the
    complement of the first, in spec order, so it can only ever name categories
    this gate actually declares.
    """
    verified = {m.category for m in measurements if m.verified}
    unverified = [spec.key for spec in CATEGORIES if spec.key not in verified]
    return round(len(verified) / len(CATEGORIES), 4), unverified


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
        )

    total_weight = sum(m.weight for m in verified)
    weighted = sum(_unit_score(m) * m.weight for m in verified)
    score = round((weighted / total_weight) * 10.0, 1) if total_weight else 0.0

    passed = sum(1 for m in verified if m.passed)
    within = round(passed / len(verified), 4)

    critical_deviations = [m.deviation or 0.0 for m in verified if m.weight == WEIGHT_CRITICAL]
    max_critical = round(max(critical_deviations), 2) if critical_deviations else 0.0

    # A critical category is only "unverified" if the run never measured it on ANY
    # element. Per-element absence is normal — a text node has no explicit padding
    # row, a frame has no font — and escalating on that made every realistic run
    # INCONCLUSIVE, which would block ships the gate exists to let through.
    verified_categories = {m.category for m in verified}
    unverified_critical = sorted(
        {
            s["category"]
            for s in skipped
            if s["category"] in CRITICAL_CATEGORY_KEYS
            and s["reason"] == "absent_from_design"
            and s["category"] not in verified_categories
        }
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
        report.reason = "critical property not exposed by the design source: " + ", ".join(unverified_critical)
        return report

    if (
        score >= PASS_SCORE_MIN
        and within >= PASS_WITHIN_TOLERANCE_PCT
        and max_critical <= PASS_CRITICAL_MAX_DEVIATION_PX
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
        f"elements={report.elements} coverage={coverage} viewport={report.viewport_binding or 'n/a'} "
        f"backend={report.backend or 'n/a'}"
    )
    # Named, not just counted: a PASS must be quotable together with the parts of the
    # gate it did not reach, otherwise "PASS" reads as "everything was checked".
    if report.unverified_categories:
        line += f" unverified={','.join(report.unverified_categories)}"
    return line


# --- Gate runner (the join §3.3 exists for) ---------------------------------


def resolve_design_source(source: Path, backend: str, node_ids: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    """Extract per-node facts from a raw design artefact.

    `source` is a `get_figma_data` response for `figma`, or a `.op` document for
    `openpencil`. The backend is never inferred from the file's shape: guessing
    would silently pick the wrong extractor and produce plausible-but-wrong
    numbers, and §3's backend contract is fail-closed for the same reason.
    """
    if backend == "figma":
        return parse_figma_facts(Path(source).read_text(encoding="utf-8"), node_ids)
    if backend == "openpencil":
        return parse_op_facts(Path(source), node_ids)
    raise ValueError(f"unknown design backend {backend!r}: expected 'figma' or 'openpencil'")


def join_by_map(
    design_map: Dict[str, Any],
    design_facts: Dict[str, Any],
    dom_facts: Dict[str, Any],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Re-key both sides by element key, using the map as the only join.

    Design nodes and DOM elements cannot be matched by inference (§3.3), so the
    map is the sole source of truth: `{element_key: {design_node, selector}}`.

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
            design_out[element] = design_facts[node]
        if selector in dom_facts:
            dom_out[element] = dom_facts[selector]

    return design_out, dom_out


def exit_code(report: Report) -> int:
    """Process exit status for the runner.

    INCONCLUSIVE deliberately does not share 0 with PASS: a caller that only
    checks the exit code must never read "could not verify" as "verified".
    """
    return _EXIT_CODES.get(report.verdict, 1)


def run_check(
    design_map: Dict[str, Any],
    design_facts: Dict[str, Any],
    dom_facts: Dict[str, Any],
    *,
    backend: str = "",
    breakpoint: str = "",
    design_viewport: Optional[int] = None,
    dom_viewport: Optional[int] = None,
) -> Report:
    """Run the gate end to end: join both sides and apply §1/§2's rules.

    `design_facts` is keyed by design node id, `dom_facts` by CSS selector; both
    are the flat per-node form the extractors emit (not the §3.1 nested document,
    which is the human-facing record). `breakpoint` is carried into the report as
    provenance only.

    The viewports are a precondition, not provenance. A design captured at 375px
    compared against a DOM measured at 1440px is not a nearly-passing run — every
    number it produces is meaningless, so that is refused here rather than scored
    and reported with a reassuring score next to it.
    """
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
    return report


def iter_categories() -> Iterable[CategorySpec]:
    return CATEGORIES
