"""Ingest an external wireframe into Che's normalised wireframe IR.

WHY THIS EXISTS
---------------
Che could only *produce* wireframes (MODE B / ux playbook Phase 1). This module adds the missing
front door: read a designer's ``.excalidraw`` file and emit a source-agnostic intermediate
representation (IR) that the rest of the design pipeline (theme extraction, tokens, screens)
consumes. The IR is the contract every source adapter must honour — see
``domains/ux/templates/wireframe-ir.schema.json``.

Parsing is deterministic and stdlib-only: no LLM, no network, no new dependency.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set

from che_core.diagnostics import fail

#: IR schema version — bumped only when the IR shape changes incompatibly.
IR_VERSION = 1

_ARROW = "arrow"
_FRAME = "frame"
_TEXT = "text"


def _bbox(element: Dict[str, Any]) -> Dict[str, float]:
    return {
        "x": element.get("x", 0),
        "y": element.get("y", 0),
        "w": element.get("width", 0),
        "h": element.get("height", 0),
    }


def _normalise(element: Dict[str, Any], labels: Dict[str, str]) -> Dict[str, Any]:
    """Normalise one Excalidraw element into an IR element.

    A-1 invariant: a normalised element MUST carry a non-empty id; a nameless node is impossible
    for a correctly parsed document, so it crashes rather than propagating a broken element.
    """
    element_id = element.get("id")
    assert isinstance(element_id, str) and element_id, "A-1: element id must be a non-empty string after normalisation"
    return {
        "id": element_id,
        "type": element.get("type"),
        "bbox": _bbox(element),
        "label": labels.get(element_id),
        "role": None,
    }


def _is_bound(element: Dict[str, Any]) -> bool:
    return bool(element.get("startBinding")) and bool(element.get("endBinding"))


def _relation(element: Dict[str, Any], ids: Set[str]) -> Dict[str, Any]:
    """Turn a bound arrow into an IR relation.

    A-2 invariant: both endpoints MUST resolve to an IR element id; a dangling endpoint means the
    binding resolution is wrong, which is impossible for a correct parse.
    """
    from_id = element["startBinding"].get("elementId")
    to_id = element["endBinding"].get("elementId")
    assert from_id in ids and to_id in ids, "A-2: relation endpoints must reference existing IR element ids"
    return {"from_id": from_id, "to_id": to_id, "kind": _ARROW}


def build_ir(document: Dict[str, Any], source_name: str) -> Dict[str, Any]:
    """Build the normalised IR from a parsed Excalidraw document (pure).

    PRE: ``document`` is a parsed JSON object whose ``elements`` list is non-empty.
    POST: returns ``{version, source, frames, elements, relations}`` where every relation endpoint
    resolves to an element id. Raises ``CheError(WIREFRAME_INVALID)`` on an unusable document.
    """
    if not isinstance(document, dict):
        fail("WIREFRAME_INVALID", path=source_name, detail="root is not a JSON object")
    raw = document.get("elements")
    if not isinstance(raw, list) or not raw:
        fail("WIREFRAME_INVALID", path=source_name, detail="missing or empty `elements` array")

    visible = [element for element in raw if isinstance(element, dict) and not element.get("isDeleted", False)]
    labels = {
        element["containerId"]: element.get("text", "")
        for element in visible
        if element.get("type") == _TEXT and element.get("containerId")
    }
    frames = [_normalise(element, labels) for element in visible if element.get("type") == _FRAME]
    shapes = [
        element
        for element in visible
        if element.get("type") not in (_ARROW, _FRAME)
        and not (element.get("type") == _TEXT and element.get("containerId"))
    ]
    elements = [_normalise(element, labels) for element in shapes]
    ids = {element["id"] for element in elements}
    relations = [_relation(element, ids) for element in visible if element.get("type") == _ARROW and _is_bound(element)]

    return {
        "version": IR_VERSION,
        "source": {"format": "excalidraw", "name": source_name},
        "frames": frames,
        "elements": elements,
        "relations": relations,
    }


def ingest_wireframe(wireframe_path: str, out_path: str) -> int:
    """Read an ``.excalidraw`` file and write its IR to ``out_path`` (imperative shell).

    PRE: ``wireframe_path`` names a readable JSON file; ``out_path`` is a writable destination.
    POST: ``out_path`` holds the IR and the function returns 0; on any failure nothing is written.
    """
    if not isinstance(wireframe_path, str) or not wireframe_path:
        fail("MISSING_ARTIFACT_ARGUMENT", helper="ingest wireframe", argument="wireframe_path")
    if not isinstance(out_path, str) or not out_path:
        fail("MISSING_ARTIFACT_ARGUMENT", helper="ingest wireframe", argument="--out")

    source = Path(wireframe_path)
    if not source.is_file():
        fail("UNREADABLE_INPUT", path=str(source), detail="file not found")
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail("INVALID_JSON", path=str(source), detail=str(exc))
    except (OSError, UnicodeDecodeError) as exc:
        fail("UNREADABLE_INPUT", path=str(source), detail=str(exc))

    ir = build_ir(document, source.name)

    destination = Path(out_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(ir, indent=2) + "\n", encoding="utf-8")

    print(f"CHE_IR_FILE={destination}")
    print(f"CHE_IR_ELEMENTS={len(ir['elements'])}")
    print(f"CHE_IR_RELATIONS={len(ir['relations'])}")
    return 0


_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _validate_element(index: int, element: Any, issues: List[str]) -> None:
    if not isinstance(element, dict):
        issues.append(f"elements[{index}]: not an object")
        return
    if not isinstance(element.get("id"), str) or not element["id"]:
        issues.append(f"elements[{index}]: missing non-empty `id`")
    if not isinstance(element.get("type"), str):
        issues.append(f"elements[{index}]: missing `type`")
    bbox = element.get("bbox")
    if not isinstance(bbox, dict) or not all(isinstance(bbox.get(key), (int, float)) for key in ("x", "y", "w", "h")):
        issues.append(f"elements[{index}]: `bbox` must hold numeric x/y/w/h")


def validate_ir(ir_path: str) -> int:
    """Validate an IR document against the wireframe IR contract (a verdict, not a failure).

    PRE: ``ir_path`` names an existing readable JSON file.
    POST: prints ``errors=N`` plus one line per issue; returns 0 when N == 0, else 1.
    """
    if not isinstance(ir_path, str) or not ir_path:
        fail("MISSING_ARTIFACT_ARGUMENT", helper="ir validate", argument="ir_path")
    path = Path(ir_path)
    if not path.is_file():
        fail("UNREADABLE_INPUT", path=str(path), detail="file not found")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail("INVALID_JSON", path=str(path), detail=str(exc))
    except (OSError, UnicodeDecodeError) as exc:
        fail("UNREADABLE_INPUT", path=str(path), detail=str(exc))

    issues: List[str] = []
    if not isinstance(document, dict):
        issues.append("root: not a JSON object")
    else:
        if document.get("version") != IR_VERSION:
            issues.append(f"version: expected {IR_VERSION}")
        source = document.get("source")
        if (
            not isinstance(source, dict)
            or not isinstance(source.get("format"), str)
            or not isinstance(source.get("name"), str)
        ):
            issues.append("source: must hold string `format` and `name`")
        elements = document.get("elements")
        if not isinstance(elements, list):
            issues.append("elements: missing or not an array")
            elements = []
        else:
            for index, element in enumerate(elements):
                _validate_element(index, element, issues)
        for index, element in enumerate(document.get("frames") or []):
            _validate_element(index, element, issues)
        ids = {
            element["id"] for element in elements if isinstance(element, dict) and isinstance(element.get("id"), str)
        }
        relations = document.get("relations")
        if not isinstance(relations, list):
            issues.append("relations: missing or not an array")
        else:
            for index, relation in enumerate(relations):
                if not isinstance(relation, dict):
                    issues.append(f"relations[{index}]: not an object")
                    continue
                for side in ("from_id", "to_id"):
                    endpoint = relation.get(side)
                    if endpoint not in ids:
                        issues.append(f"relations[{index}].{side}: {endpoint!r} is not an element id")

    print(f"errors={len(issues)}")
    for issue in issues:
        print(f"  - {issue}")
    return 0 if not issues else 1


def ingest_theme(worktree_root: str, sub_product: str, colors_path: str) -> int:
    """Patch the canonical tokens.json with a proposed colour theme (imperative shell).

    PRE: the worktree holds a design tree (``che designer init`` ran); ``colors_path`` is a JSON
    object either ``{"colors": {...}}`` or a flat ``{name: hex}`` map.
    POST: ``design/tokens/tokens.json`` carries the proposed colours and returns 0; on any failure
    nothing is written (INV-1).
    """
    if not isinstance(worktree_root, str) or not worktree_root:
        fail("MISSING_WORKTREE_ROOT")
    if not isinstance(sub_product, str) or not sub_product:
        fail("INVALID_SUB_PRODUCT_SLUG", sub_product=sub_product, pattern="non-empty slug")
    if not isinstance(colors_path, str) or not colors_path:
        fail("MISSING_ARTIFACT_ARGUMENT", helper="ingest theme", argument="--colors")

    worktree = Path(worktree_root).resolve()
    if not worktree.is_dir():
        fail("NOT_A_DIRECTORY", path=worktree)

    tokens_path = worktree / "design" / "tokens" / "tokens.json"
    if not tokens_path.is_file():
        fail("TOKENS_JSON_MISSING", path=tokens_path)

    colors_file = Path(colors_path)
    if not colors_file.is_file():
        fail("UNREADABLE_INPUT", path=str(colors_file), detail="file not found")
    try:
        proposed = json.loads(colors_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail("INVALID_JSON", path=str(colors_file), detail=str(exc))
    except (OSError, UnicodeDecodeError) as exc:
        fail("UNREADABLE_INPUT", path=str(colors_file), detail=str(exc))

    if not isinstance(proposed, dict):
        fail("THEME_INVALID", path=str(colors_file), detail="root is not a JSON object")
    palette = proposed.get("colors", proposed)
    if not isinstance(palette, dict) or not palette:
        fail("THEME_INVALID", path=str(colors_file), detail="no colours found")
    for name, value in palette.items():
        if not isinstance(value, str) or not _HEX_RE.match(value):
            fail("THEME_INVALID", path=str(colors_file), detail=f"{name}={value!r} is not a #RRGGBB colour")

    tokens = json.loads(tokens_path.read_text(encoding="utf-8"))
    tokens.setdefault("colors", {})
    tokens["colors"].update(palette)
    tokens["sub_product"] = sub_product
    tokens_path.write_text(json.dumps(tokens, indent=2) + "\n", encoding="utf-8")

    print(f"CHE_TOKENS_FILE={tokens_path}")
    print(f"CHE_TOKENS_COLORS={len(tokens['colors'])}")
    return 0
