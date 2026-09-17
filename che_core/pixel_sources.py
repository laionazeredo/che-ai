"""Design-side fact extractors for the pixel-check engine.

Two extractors, resolved fail-closed by `DESIGN_BACKEND_CONTRACT.md` and never
converted into one another. A third design tool is declared first-class by the UX
domain — Penpot — and has deliberately **no** extractor here: its MCP server exposes
`execute_code` rather than a fact-export tool, so a bag would have to be recorded from
a real session and pinned by a fixture before any number it produced could be trusted.
Writing that parser against a guessed schema is the exact mistake §4 of the gate warns
about, so until the recording exists `penpot` is *refused by name* (see
:data:`BACKENDS_WITHOUT_EXTRACTOR`) rather than failing as an unknown string — the
difference between "this tool cannot be read yet" and "you spelled the flag wrong":

* ``openpencil`` — reads a ``.op`` document. It is plain JSON, so this is the
  robust path: no vendor text format to reverse-engineer, and it is the harness's
  declared git-able design source of truth.
* ``figma`` — reads the indented text that ``mcp_Figma_AI_Bridge.get_figma_data``
  returns. That format is a *rendering*, not a schema, so the parser is glued to
  the field names observed in a real response and pinned by a recorded fixture;
  a format change breaks a test rather than silently producing wrong numbers.

Both emit the same normalised property bag consumed by :mod:`che_core.pixel`, and
both **omit** a property the backend does not expose rather than defaulting it to
zero. Omitting is what lets the comparator mark a category unverified instead of
scoring a comparison against an invented value.

Coverage differs by backend, measured against the gate's §1 table. `no` means **no code path
emits the property at all** — a structural gap. A property that only one *sampled document*
lacks is a different thing and is marked as such, because conflating the two turns a fact
about a test fixture into a claim about a tool:

===============  ===========  =============
section          openpencil   figma bridge
===============  ===========  =============
box / position   yes          yes
padding          yes          yes
radius           yes          yes
border           no           yes
typography       yes          yes †
colours          yes          yes
shadow           no           yes
===============  ===========  =============

† Both parsers read `letterSpacing`; the sampled bridge response carries none, so #9 is
unverified for *that document* rather than for the backend.

`margin` appears in neither design column. Auto-layout replaced it with `gap` (#14), so
`margin` is declared **unreachable** rather than merely unmeasured: it is excluded from the
`coverage` denominator and named in the report. See
`che_core.pixel.UNREACHABLE_CATEGORY_KEYS` for why the exclusion is a disclosure and not a
silent discount.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# --- the backend vocabulary ------------------------------------------------

#: Design backends this module can actually read.
BACKENDS_WITH_EXTRACTOR = frozenset({"figma", "openpencil"})

#: Design backends the UX domain declares but that nothing here can read.
#:
#: Keep them separate from "unknown": a caller who asks for `penpot` is not mistaken,
#: only early — `domains/ux/connectors/penpot.config.md` documents it as a first-class
#: alternative to Figma, and it genuinely is, for the parts of the domain that need a
#: design tool rather than a numeric fact bag. Refusing it by name keeps the reply
#: actionable; treating it as a typo sends the caller to check their spelling against
#: documentation that told them the opposite.
BACKENDS_WITHOUT_EXTRACTOR = frozenset({"penpot"})

#: Every backend name a caller may legitimately say out loud. Used for CLI vocabularies,
#: so an unimplemented backend reaches the code that can explain itself instead of being
#: rejected by the argument parser with a message shaped like a typo.
DECLARED_BACKENDS = tuple(sorted(BACKENDS_WITH_EXTRACTOR | BACKENDS_WITHOUT_EXTRACTOR))

# --- shared helpers ---------------------------------------------------------

#: Coordinates measured relative to the element's own parent/anchor. Figma's
#: `locationRelativeToParent` is exactly this.
COORD_FRAME_PARENT = "parent"

#: Declares that no comparable coordinates exist for this node. An `.op` document
#: is auto-layout: children are laid out by the tool, so they carry no x/y at all.
COORD_FRAME_NONE = "none"

#: The `layout.mode` values that make a Figma node an auto-layout container.
#:
#: Padding exists *only* on such a node, and the bridge omits a property whose
#: value is zero — so here an absent `padding` is a **declared 0**, not a withheld
#: value. Reading it as withheld made a ×2 critical category unverifiable on every
#: auto-layout screen, which returned INCONCLUSIVE on a page where every other
#: property was measurable (§2.5).
FIGMA_AUTO_LAYOUT_MODES = frozenset({"row", "column", "grid"})

#: The same notion in `.op`, which names the axis `layout` and likewise omits a
#: zero `padding`.
OP_AUTO_LAYOUT_MODES = frozenset({"vertical", "horizontal", "grid"})

#: Node kinds that render as a *box*, and therefore have a corner radius at all.
#:
#: Same rule as padding: a box always has a radius, and both backends leave the
#: property out when it is zero — so its absence is a declared 0. A text node, a
#: vector or an ellipse has no radius concept, so nothing is invented for them.
BOX_NODE_KINDS = frozenset({"frame", "rectangle", "instance", "component", "group"})

#: The bridge reports `opacity` only when a node is not fully opaque, so an absent
#: value means 1.0 rather than "unknown". Reading it as unknown would leave the
#: category unverified on every element, and an element that is correctly sized,
#: positioned and invisible is exactly the failure §6.1 admits the gate cannot see.
DEFAULT_OPACITY = 1.0

#: The value each backend uses for "this text box takes the text's own size".
#:
#: §1 #18 needs it because a line count is only knowable where wrapping *cannot* happen.
#: When the box hugs its content, the rendered lines are exactly the text's own breaks, so
#: the design can state a count; when the box has a fixed or filled width the text wraps at
#: a width the design does not report and any count would be an invention. Figma spells it
#: `sizing.horizontal: "hug"`, `.op` spells it `textGrowth: "auto"`.
FIGMA_TEXT_SIZING_HUG = "hug"
OP_TEXT_GROWTH_AUTO = "auto"

_PX_RE = re.compile(r"^-?\d+(?:\.\d+)?px$")


def _px(value: Any) -> Optional[float]:
    """``"16px"`` / ``16`` / ``16.0`` -> ``16.0``; anything else -> ``None``."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if _PX_RE.match(text):
            return float(text[:-2])
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _ratio(value: Any) -> Optional[float]:
    """Parse a line-height ratio: ``1.45``, ``"1.45"``, ``"1.45em"``, ``"145%"``.

    The gate's tolerance for #8 is a *ratio* (≤ 0.05 leading), and the design
    sources express it as a multiplier while a browser reports pixels — so both
    sides are normalised to a ratio (the DOM side divides by its own font size).
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    try:
        if text.endswith("%"):
            return float(text[:-1]) / 100.0
        if text.endswith("em"):
            return float(text[:-2])
        if text == "normal":
            return None
        return float(text)
    except ValueError:
        return None


def _first_color(fills: Any) -> Optional[str]:
    """First resolvable colour from a fill list, or ``None`` (gradients, images)."""
    if not isinstance(fills, (list, tuple)):
        fills = [fills]
    for fill in fills:
        if isinstance(fill, str) and (fill.startswith("#") or fill.startswith("rgb")):
            return fill
        if isinstance(fill, dict):
            for key in ("color", "value", "hex"):
                candidate = fill.get(key)
                if isinstance(candidate, str) and (candidate.startswith("#") or candidate.startswith("rgb")):
                    return candidate
    return None


def _resolve_paint(fill: Any) -> Optional[str]:
    """One paint entry as something comparable: a flat colour, or a gradient's CSS."""
    colour = _first_color([fill])
    if colour:
        return colour
    if isinstance(fill, dict):
        for key in ("gradient", "css", "value"):
            candidate = fill.get(key)
            if isinstance(candidate, str) and "gradient(" in candidate:
                return candidate
    return None


def _paint_stack(fills: Any) -> Optional[List[str]]:
    """Every paint in a fill list, **bottom-to-top**, or ``None`` when it is not comparable.

    This replaces ``_first_paint``, which returned the first *resolvable* entry. On a node with
    two fills that is the bottom layer alone, so an implementation that dropped the top layer — a
    tint over a base, a gradient over a colour — was compared against the base and **passed**. That
    is the truncation §6.1 listed as "stacked fills are outside §1", and what it hides is worse than
    a gap: a confident match. It is also how a gradient design once passed against a flat
    implementation, one fill earlier.

    Two rules make the replacement fail closed rather than quietly partial:

    * **Every** entry must resolve to a comparable paint. An image fill is not comparable, and
      skipping it would shift the indices so layer *n* of one side was compared against layer *n-1*
      of the other — a wrong pair reported as a deviation. Non-comparable input omits the property,
      which the comparator reports as unverified. Note this is a coverage *loss* on such nodes and
      still the correct trade: the value it replaces was misleading, not merely incomplete.
    * The result is ordered bottom-to-top, the direction the design side states natively (Figma's
      ``fills[0]`` is the bottom layer). The DOM side re-orders to match — CSS lists
      ``background-image`` top-first with ``background-color`` underneath everything. A caller that
      cannot establish its source's direction must not call this with a stack; see
      :func:`parse_op_facts`.
    """
    if fills is None:
        return None
    if not isinstance(fills, (list, tuple)):
        fills = [fills]
    if not fills:
        return None
    resolved: List[str] = []
    for fill in fills:
        paint = _resolve_paint(fill)
        if paint is None:
            return None
        resolved.append(paint)
    return resolved


def _shadow_from_css(value: str) -> Optional[Dict[str, float]]:
    """Parse ``"0px 2px 8px 0px rgba(0,0,0,0.08)"`` into the gate's five axes."""
    if not isinstance(value, str):
        return None
    rgba = re.search(r"rgba?\(([^)]*)\)", value)
    lengths = [float(m) for m in re.findall(r"(-?\d+(?:\.\d+)?)px", value)]
    if len(lengths) < 2:
        return None
    alpha = 1.0
    if rgba:
        parts = [p.strip() for p in rgba.group(1).split(",")]
        if len(parts) == 4:
            try:
                alpha = float(parts[3])
            except ValueError:
                return None
    return {
        "x": lengths[0],
        "y": lengths[1],
        "blur": lengths[2] if len(lengths) > 2 else 0.0,
        "spread": lengths[3] if len(lengths) > 3 else 0.0,
        "alpha": alpha,
    }


def _shorthand(values: Any) -> Optional[List[float]]:
    """CSS shorthand (``"20px 40px"``) or list -> ``[top, right, bottom, left]``."""
    if isinstance(values, str):
        try:
            nums = [float(p.replace("px", "")) for p in values.split() if p.strip()]
        except ValueError:
            return None
    elif isinstance(values, (list, tuple)):
        try:
            nums = [float(v) for v in values]
        except (TypeError, ValueError):
            return None
    elif isinstance(values, (int, float)) and not isinstance(values, bool):
        nums = [float(values)]
    else:
        return None
    if not nums:
        return None
    if len(nums) == 1:
        return nums * 4
    if len(nums) == 2:
        return [nums[0], nums[1], nums[0], nums[1]]
    if len(nums) == 4:
        return nums
    return None


def _gap_list(value: Any) -> Optional[List[float]]:
    """Auto-layout gap -> ``[row]`` or ``[row, column]``.

    A uniform gap is written as one value and an axis pair as two; a single value
    is deliberately *not* broadcast here, so the comparator's own coercion stays
    the one place that decides how a short list fills its axes.
    """
    if isinstance(value, str):
        try:
            nums = [float(p) for p in value.replace("px", " ").split() if p.strip()]
        except ValueError:
            return None
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        nums = [float(value)]
    else:
        return None
    if not nums or len(nums) > 2:
        return None
    return nums


# --- OpenPencil (.op) --------------------------------------------------------

#: `.op` pads a frame with a 1/2/4-value array and stores a single corner radius.
_OP_PROPERTY_MAP = {
    "fontSize": "font_size",
    "fontWeight": "font_weight",
    "lineHeight": "line_height",
    "letterSpacing": "letter_spacing",
}


def _op_node_facts(node: Dict[str, Any]) -> Dict[str, Any]:
    facts: Dict[str, Any] = {}
    node_type = node.get("type")
    # `kind` is an annotation, not a category: it tells the comparator whether
    # typography applies, so a frame's missing font is "not applicable" instead of
    # an unverified ×2 gap. No CATEGORIES row measures it.
    if isinstance(node_type, str) and node_type:
        facts["kind"] = node_type.lower()

    width, height = _px(node.get("width")), _px(node.get("height"))
    box_size = {k: v for k, v in (("width", width), ("height", height)) if v is not None}
    if box_size:
        facts["box_size"] = box_size

    # No `box_origin`: an `.op` document is an auto-layout tree. Children carry no
    # coordinates at all (`fill_container` / `fit_content`), and the only node with
    # an x/y is the root, sitting at its own origin. That 0,0 is not a measured
    # position, so emitting it produced a guaranteed false FAIL the moment the DOM
    # side reported a real viewport coordinate. Position is declared unobtainable
    # here rather than approximated.
    facts["coord_frame"] = COORD_FRAME_NONE

    padding = _shorthand(node.get("padding"))
    if padding is None and node.get("layout") in OP_AUTO_LAYOUT_MODES:
        # A container always has a padding; a zero one is simply not written down.
        padding = [0.0, 0.0, 0.0, 0.0]
    if padding is not None:
        facts["padding"] = padding

    gap = _gap_list(node.get("gap"))
    if gap is not None:
        facts["gap"] = gap

    radius = _px(node.get("cornerRadius"))
    if radius is None and node_type in BOX_NODE_KINDS:
        # A box always has a corner radius; a zero one is not written down.
        radius = 0.0
    if radius is not None:
        facts["radius"] = [radius] * 4

    # Read through the stack reader, so an unresolvable fill (an image) omits the property
    # rather than standing in for it. A stack is emitted only when it holds one paint: `.op`
    # documents neither the direction of `fill` nor where a stack's paint order comes from, and
    # guessing it inverts the comparison instead of failing it. One paint has no order, which is
    # why every node in the sampled documents is readable.
    stack = _paint_stack(node.get("fill"))
    if stack is not None and len(stack) > 1:
        stack = None
    if node_type != "text" and stack:
        facts["bg"] = stack
    if node_type == "text" and stack:
        facts["fg"] = stack[-1]

    # §1 #18 — text reflow. A count is knowable only where wrapping cannot happen, and
    # `textGrowth: auto` is exactly that statement: the box is the text's own size, so the
    # rendered lines are the text's own breaks and nothing else. A `fixed-width` box wraps at a
    # width the document never states, and a node with no `content` leaves even the breaks
    # unknown — both omit the property, which the comparator reports as unverified rather than
    # scoring a line count nobody stated.
    if node_type == "text" and node.get("textGrowth") == OP_TEXT_GROWTH_AUTO:
        content = node.get("content")
        if isinstance(content, str):
            facts["line_count"] = content.count("\n") + 1

    for source, target in _OP_PROPERTY_MAP.items():
        raw = node.get(source)
        numeric = _px(raw)
        if numeric is not None:
            facts[target] = numeric
        elif isinstance(raw, (int, float)) and not isinstance(raw, bool):
            facts[target] = float(raw)

    family = node.get("fontFamily")
    if isinstance(family, str) and family.strip():
        facts["font_family"] = family.strip()

    # Read only when the document carries the key, and nothing is defaulted: the sampled
    # `.op` documents have no opacity, and asserting 1.0 there would be a fabrication
    # rather than a measurement.
    opacity = _px(node.get("opacity"))
    if opacity is not None:
        facts["opacity"] = opacity

    return facts


def parse_op_facts(document: Any, node_ids: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    """Extract normalised facts for ``node_ids`` from a ``.op`` document.

    Accepts a parsed document, a raw JSON string, or a path to a ``.op`` file.
    Returns ``{node_id: facts}``; ids not found are simply absent from the map.
    """
    if isinstance(document, (str, Path)):
        # A string may be either inline JSON or a path. Test for JSON explicitly,
        # otherwise a non-object payload such as "[1, 2, 3]" is handed to the
        # filesystem and surfaces as FileNotFoundError instead of the contract
        # error the caller is owed.
        if isinstance(document, str) and document.lstrip()[:1] in ("{", "["):
            document = json.loads(document)
        else:
            document = json.loads(Path(document).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("parse_op_facts: expected an object at the document root")

    wanted = set(node_ids)
    roots: List[Any] = []
    for key in ("children", "pages"):
        value = document.get(key)
        if isinstance(value, list):
            roots.extend(value)

    out: Dict[str, Dict[str, Any]] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            node_id = node.get("id")
            if isinstance(node_id, str) and node_id in wanted:
                out[node_id] = _op_node_facts(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for root in roots:
        walk(root)
    return out


# --- Figma AI bridge (indented text) ----------------------------------------


def _sections(payload: str) -> Dict[str, List[str]]:
    """Split the response into its ``NAME`` / ``GLOBAL_VARS`` / ``ELEMENTS`` / ... blocks."""
    headers = ("NAME", "GLOBAL_VARS", "ELEMENTS", "COMPONENTS", "NODES")
    out: Dict[str, List[str]] = {name: [] for name in headers}
    current: Optional[str] = None
    for line in payload.splitlines():
        stripped = line.rstrip()
        if stripped in headers or (stripped.endswith(":") and stripped[:-1] in headers):
            current = stripped.rstrip(":")
            continue
        if current:
            out[current].append(line)
    return out


def _parse_indented(lines: List[str]) -> Dict[str, Any]:
    """Parse the GLOBAL_VARS/ELEMENTS/COMPONENTS blocks: an indentation-keyed tree.

    Handles the two shapes present in a real response: nested maps
    (``layout_*: {mode, sizing, dimensions}``) and scalar lists
    (``fill_*:\\n  - '#FFFFFF'``). The container type cannot be known from the key
    line alone — it is chosen by peeking at the next non-empty line, because a
    key with no inline value is followed either by ``- item`` or by ``child:``.
    """
    root: Dict[str, Any] = {}
    stack: List[Tuple[int, Any]] = [(-1, root)]

    for pos, raw in enumerate(lines):
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        text = raw.strip()

        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        container = stack[-1][1]

        if text.startswith("- "):
            # The list itself is the nearest stack entry (pushed by its key line).
            target = next((candidate for _, candidate in reversed(stack) if isinstance(candidate, list)), None)
            if target is None:
                continue
            item = text[2:].strip()
            key, separator, remainder = item.partition(":")
            # A list item is usually a bare scalar (`- '#FFFFFF'`), but a
            # multi-property one — a gradient fill, for instance — opens with a
            # `key: value` line whose more-indented siblings belong to the same entry.
            # Appending it as a raw string dropped the gradient's own definition, so
            # the paint was recorded absent and a gradient design could never fail.
            if separator and remainder.strip() and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key.strip()):
                entry: Dict[str, Any] = {key.strip(): remainder.strip().strip("'\"")}
                target.append(entry)
                stack.append((indent, entry))
                continue
            target.append(item.strip("'\""))
            continue

        if ":" not in text:
            continue
        key, _, remainder = text.partition(":")
        key, remainder = key.strip(), remainder.strip()

        if not remainder:
            child: Any = {}
            for look in lines[pos + 1 :]:
                if not look.strip():
                    continue
                if len(look) - len(look.lstrip(" ")) > indent and look.strip().startswith("- "):
                    child = []
                break
            if isinstance(container, dict):
                container[key] = child
            stack.append((indent, child))
            continue

        value: Any = remainder.strip("'\"")
        if not isinstance(container, dict):
            continue
        if value.startswith("{") or value.startswith("["):
            try:
                container[key] = json.loads(value)
                continue
            except json.JSONDecodeError:
                pass
        container[key] = value

    return root


_NODE_LINE_RE = re.compile(
    r'^(?P<indent>\s*)\[(?P<type>[A-Za-z_-]+)\]\s*(?:"(?P<name>[^"]*)"\s*)?#(?P<id>\S+)\s*(?P<attrs>.*)$'
)


def _join_wrapped(lines: List[str]) -> List[str]:
    """Re-join node lines that were split inside a quoted value.

    A ``text="...`` value whose content contains a newline ends the source line
    mid-quote. Without rejoining, the tokenizer consumes the truncated value and
    every attribute that followed it on the continued line is silently dropped.
    """
    out: List[str] = []
    for raw in lines:
        if out and out[-1].count('"') % 2 == 1:
            out[-1] = f"{out[-1]}\n{raw}"
            continue
        out.append(raw)
    return out


def _tokenize_attrs(text: str) -> Dict[str, Any]:
    """Split ``key=value`` pairs where a value may be ``{json}``, ``"quoted"`` or bare."""
    out: Dict[str, Any] = {}
    i, length = 0, len(text)
    while i < length:
        while i < length and text[i].isspace():
            i += 1
        start = i
        while i < length and not text[i].isspace() and text[i] != "=":
            i += 1
        key = text[start:i]
        if not key or i >= length or text[i] != "=":
            i += 1
            continue
        i += 1  # consume '='
        if i < length and text[i] in "{[":
            # Inline JSON: `layout={...}` objects and `fills=["#6D28D9"]` lists.
            opener, closer = text[i], "}" if text[i] == "{" else "]"
            depth, begin = 0, i
            while i < length:
                if text[i] == opener:
                    depth += 1
                elif text[i] == closer:
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                i += 1
            try:
                out[key] = json.loads(text[begin:i])
            except json.JSONDecodeError:
                out[key] = text[begin:i]
        elif i < length and text[i] == '"':
            i += 1
            begin = i
            while i < length and text[i] != '"':
                i += 1
            out[key] = text[begin:i]
            i += 1
        else:
            begin = i
            while i < length and not text[i].isspace():
                i += 1
            raw = text[begin:i]
            if "," in raw and not raw.startswith("["):
                out[key] = raw
            else:
                numeric = _px(raw)
                out[key] = numeric if numeric is not None else raw
    return out


def _resolve(node_attrs: Dict[str, Any], globals_: Dict[str, Any], elements: Dict[str, Any]) -> Dict[str, Any]:
    """Replace token references with their GLOBAL_VARS/ELEMENTS definitions."""
    resolved: Dict[str, Any] = dict(node_attrs)

    def deref(value: Any) -> Any:
        if isinstance(value, str):
            if value in globals_:
                return globals_[value]
            if value in elements:
                return elements[value]
        return value

    for key in list(resolved):
        resolved[key] = deref(resolved[key])

    template = resolved.pop("template", None)
    if isinstance(template, dict):
        for key, value in template.items():
            resolved.setdefault(key, value)
    return resolved


def _figma_node_facts(node: Dict[str, Any]) -> Dict[str, Any]:
    facts: Dict[str, Any] = {}
    layout = node.get("layout") if isinstance(node.get("layout"), dict) else {}

    # See `_op_node_facts`: `kind` gates applicability, it is not measured. Figma
    # spells it in caps ("TEXT"), the .op side in lower case, so it is normalised
    # here to keep `_is_text` from having to know either vendor's convention.
    node_type = node.get("type")
    if isinstance(node_type, str) and node_type:
        facts["kind"] = node_type.lower()

    dimensions = layout.get("dimensions") if isinstance(layout.get("dimensions"), dict) else {}
    box_size = {
        k: v
        for k, v in (("width", _px(dimensions.get("width"))), ("height", _px(dimensions.get("height"))))
        if v is not None
    }
    if box_size:
        facts["box_size"] = box_size

    # Coordinates are declared with the frame they live in. The DOM side reports
    # `getBoundingClientRect()` (viewport-relative), so without this the comparator
    # would difference two different origins and emit a confident, meaningless
    # number. See `_position_is_comparable`.
    facts["coord_frame"] = COORD_FRAME_PARENT
    where = layout.get("locationRelativeToParent") if isinstance(layout.get("locationRelativeToParent"), dict) else {}
    box_origin = {k: v for k, v in (("x", _px(where.get("x"))), ("y", _px(where.get("y")))) if v is not None}
    if box_origin:
        facts["box_origin"] = box_origin

    padding = _shorthand(layout.get("padding")) if layout.get("padding") is not None else None
    if padding is None and layout.get("mode") in FIGMA_AUTO_LAYOUT_MODES:
        # A container always has a padding; a zero one is simply not written down.
        padding = [0.0, 0.0, 0.0, 0.0]
    if padding is not None:
        facts["padding"] = padding

    gap = _gap_list(layout.get("gap"))
    if gap is not None:
        facts["gap"] = gap

    radius = _shorthand(node.get("borderRadius"))
    if radius is None:
        single = _px(node.get("borderRadius"))
        radius = [single] * 4 if single is not None else None
    if radius is None and facts.get("kind") in BOX_NODE_KINDS:
        # A box always has a corner radius; a zero one is not written down.
        radius = [0.0, 0.0, 0.0, 0.0]
    if radius is not None:
        facts["radius"] = radius

    border_width = _px(node.get("strokeWeight"))
    if border_width is not None:
        facts["border_width"] = border_width
        stroke_color = _first_color(node.get("strokes"))
        if stroke_color:
            facts["border_color"] = stroke_color

    text_style = node.get("textStyle") if isinstance(node.get("textStyle"), dict) else {}
    for source, target in (("fontSize", "font_size"), ("fontWeight", "font_weight")):
        raw = text_style.get(source, node.get(source))
        numeric = _px(raw)
        if numeric is None and isinstance(raw, (int, float)) and not isinstance(raw, bool):
            numeric = float(raw)
        if numeric is not None:
            facts[target] = numeric

    # The design sources give a multiplier ("1.45em"); a browser gives pixels, so
    # both are normalised to a ratio, which is the unit the gate's tolerance uses.
    line_height = _ratio(text_style.get("lineHeight", node.get("lineHeight")))
    if line_height is not None:
        facts["line_height"] = line_height
    # Read only when the response carries it: the sampled bridge response has no
    # `letterSpacing`, so #9 stays absent for that document — but that is a fact about the
    # document, not about the bridge, so the value is read rather than declared missing.
    spacing = node.get("letterSpacing")
    if isinstance(spacing, (int, float)) and not isinstance(spacing, bool):
        facts["letter_spacing"] = float(spacing)

    family = text_style.get("fontFamily", node.get("fontFamily"))
    if isinstance(family, str) and family.strip():
        facts["font_family"] = family.strip()

    # §1 #18, the `.op` rule in the bridge's vocabulary: `hug` means the box took the text's own
    # size, so the rendered lines are the text's own breaks. A `fill`/`fixed` box wraps at a width
    # the response does not report and the property is omitted. The sampled response states no
    # `sizing` for its TEXT nodes at all, so this is unverified for that document while the bridge
    # reads it whenever it is there — a fact about the document, not about the backend.
    sizing = layout.get("sizing") if isinstance(layout.get("sizing"), dict) else {}
    if facts.get("kind") == "text" and sizing.get("horizontal") == FIGMA_TEXT_SIZING_HUG:
        text = node.get("text")
        if isinstance(text, str):
            facts["line_count"] = text.count("\n") + 1

    # Omitting `opacity` means fully opaque, so the default *is* the measured value rather
    # than a guess — the bridge states it whenever the node is not fully opaque, unlike the
    # sampled `.op` documents, which never mention it at all.
    opacity = _px(node.get("opacity"))
    facts["opacity"] = DEFAULT_OPACITY if opacity is None else opacity

    paints = _paint_stack(node.get("fills"))
    if node.get("type") == "TEXT":
        if paints:
            facts["fg"] = paints[-1]
    elif paints:
        facts["bg"] = paints

    effects = node.get("effects")
    if isinstance(effects, dict) and "boxShadow" in effects:
        shadow = _shadow_from_css(effects["boxShadow"])
        if shadow:
            facts["shadow"] = shadow

    return facts


def parse_figma_facts(payload: str, node_ids: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    """Extract normalised facts for ``node_ids`` from a `get_figma_data` response.

    Returns ``{node_id: facts}``. Ids absent from the response are absent from the
    map, which the caller must treat as "design source did not provide this node".
    """
    blocks = _sections(payload)
    globals_ = _parse_indented(blocks["GLOBAL_VARS"])
    elements = _parse_indented(blocks["ELEMENTS"])
    wanted = set(node_ids)

    out: Dict[str, Dict[str, Any]] = {}
    for line in _join_wrapped(blocks["NODES"]):
        match = _NODE_LINE_RE.match(line)
        if not match:
            continue
        node_id = match.group("id")
        if node_id not in wanted:
            continue
        attrs = _tokenize_attrs(match.group("attrs") or "")
        attrs.setdefault("type", match.group("type").upper())
        out[node_id] = _figma_node_facts(_resolve(attrs, globals_, elements))
    return out
