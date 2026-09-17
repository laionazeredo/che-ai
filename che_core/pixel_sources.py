"""Design-side fact extractors for the pixel-check engine.

Two backends, resolved fail-closed by `DESIGN_BACKEND_CONTRACT.md` and never
converted into one another:

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

Coverage differs by backend, measured against the gate's §1 table:

===============  =========  =============
section          openpencil  figma bridge
===============  =========  =============
box / position   yes         yes
padding          yes         yes
radius           yes         yes
border           no          yes
typography       yes         no letter-spacing
colours          yes         yes
shadow           no          yes
===============  =========  =============
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# --- shared helpers ---------------------------------------------------------

#: Coordinates measured relative to the element's own parent/anchor. Figma's
#: `locationRelativeToParent` is exactly this.
COORD_FRAME_PARENT = "parent"

#: Declares that no comparable coordinates exist for this node. An `.op` document
#: is auto-layout: children are laid out by the tool, so they carry no x/y at all.
COORD_FRAME_NONE = "none"

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
    if padding is not None:
        facts["padding"] = padding

    radius = _px(node.get("cornerRadius"))
    if radius is not None:
        facts["radius"] = [radius] * 4

    background = _first_color(node.get("fill"))
    if node_type != "text" and background:
        facts["bg"] = background
    if node_type == "text":
        ink = _first_color(node.get("fill"))
        if ink:
            facts["fg"] = ink

    for source, target in _OP_PROPERTY_MAP.items():
        raw = node.get(source)
        numeric = _px(raw)
        if numeric is not None:
            facts[target] = numeric
        elif isinstance(raw, (int, float)) and not isinstance(raw, bool):
            facts[target] = float(raw)

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
            for _, candidate in reversed(stack):
                if isinstance(candidate, list):
                    candidate.append(text[2:].strip().strip("'\""))
                    break
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
    if padding is not None:
        facts["padding"] = padding

    radius = _shorthand(node.get("borderRadius"))
    if radius is None:
        single = _px(node.get("borderRadius"))
        radius = [single] * 4 if single is not None else None
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
    # The bridge emits no letterSpacing, so category #9 stays absent on purpose:
    # the comparator reports it unverified rather than comparing against a guess.
    spacing = node.get("letterSpacing")
    if isinstance(spacing, (int, float)) and not isinstance(spacing, bool):
        facts["letter_spacing"] = float(spacing)

    background = _first_color(node.get("fills"))
    if node.get("type") == "TEXT":
        if background:
            facts["fg"] = background
    elif background:
        facts["bg"] = background

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
