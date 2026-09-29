"""Tests for che_core.designer_ingest (T1 · F0 — B-1 + AB-1 + A-1/A-2).

Contract:
- B-1 (positive): a valid .excalidraw → IR with elements=3, relations=2, endpoints resolve.
- AB-1 (negative): malformed input → non-zero exit, NO output file written (INV-1).
- A-1/A-2 (assertive invariants): impossible states crash rather than emit a broken IR.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "wireframe-demo.excalidraw"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "che_core.cli", "designer", *args],
        capture_output=True,
        text=True,
        check=False,
    )


# @ac B-1 — 3 rectangles (one with a bound label) + 2 arrows → 3 elements, 2 relations
def test_build_ir_shapes_and_relations() -> None:
    """B-1: shapes become elements, bound arrows become relations with resolvable endpoints."""
    from che_core.designer_ingest import build_ir

    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ir = build_ir(document, FIXTURE.name)

    assert len(ir["elements"]) == 3, f"expected 3 shape elements; got {ir['elements']!r}"
    assert len(ir["relations"]) == 2, f"expected 2 relations; got {ir['relations']!r}"

    ids = {element["id"] for element in ir["elements"]}
    for relation in ir["relations"]:
        assert relation["from_id"] in ids, f"dangling from_id={relation['from_id']!r}"
        assert relation["to_id"] in ids, f"dangling to_id={relation['to_id']!r}"


# @ac B-1 — a bound text element is folded into its container's label, not counted as an element
def test_build_ir_folds_bound_text_into_label() -> None:
    """B-1: the rectangle labelled "Home" carries the label; the text node is not an element."""
    from che_core.designer_ingest import build_ir

    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ir = build_ir(document, FIXTURE.name)

    home = next(element for element in ir["elements"] if element["id"] == "rect-a")
    assert home["label"] == "Home", f"bound text must become the container label; got {home!r}"
    assert "text-a" not in {element["id"] for element in ir["elements"]}


# @ac AB-1 — malformed input is refused and nothing is written (INV-1)
def test_cli_ingest_malformed_writes_nothing(tmp_path: Path) -> None:
    """AB-1: a non-JSON .excalidraw → non-zero exit and no IR file on disk."""
    broken = tmp_path / "broken.excalidraw"
    broken.write_text("{ not json", encoding="utf-8")
    out = tmp_path / "ir.json"

    result = _run_cli("ingest", "wireframe", str(broken), "--out", str(out))

    assert result.returncode != 0, f"malformed input must exit non-zero; got {result.returncode}"
    assert not out.exists(), "INV-1: no IR file may be written when ingest fails"


# @ac AB-1 — a JSON document with no elements array is refused
def test_build_ir_rejects_missing_elements() -> None:
    """AB-1: valid JSON without an `elements` array is not a usable wireframe."""
    from che_core.designer_ingest import build_ir
    from che_core.diagnostics import CheError

    with pytest.raises(CheError) as excinfo:
        build_ir({"type": "excalidraw"}, "empty.excalidraw")

    assert excinfo.value.code == "WIREFRAME_INVALID"


# @ac A-1 — an element without an id is an impossible state
def test_element_without_id_crashes() -> None:
    """A-1: a parsed element with no id crashes rather than emitting a nameless node."""
    from che_core.designer_ingest import build_ir

    with pytest.raises(AssertionError):
        build_ir({"elements": [{"type": "rectangle"}]}, "bad.excalidraw")


# @ac A-2 — a relation pointing at an unknown element id is an impossible state
def test_relation_to_missing_element_crashes() -> None:
    """A-2: a bound arrow whose endpoint does not exist among elements crashes."""
    from che_core.designer_ingest import build_ir

    document = {
        "elements": [
            {"id": "rect-a", "type": "rectangle"},
            {
                "id": "arrow-x",
                "type": "arrow",
                "startBinding": {"elementId": "rect-a"},
                "endBinding": {"elementId": "ghost"},
            },
        ]
    }

    with pytest.raises(AssertionError):
        build_ir(document, "bad.excalidraw")


# @ac CLI — `che designer ingest wireframe` is registered and runs end-to-end
def test_cli_ingest_wireframe_happy_path(tmp_path: Path) -> None:
    """CLI smoke: ingest the fixture and read the IR back off disk."""
    out = tmp_path / "ir.json"

    result = _run_cli("ingest", "wireframe", str(FIXTURE), "--out", str(out))

    assert result.returncode == 0, (
        f"`che designer ingest wireframe` must exit 0; got {result.returncode}\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    ir = json.loads(out.read_text(encoding="utf-8"))
    assert len(ir["elements"]) == 3
    assert len(ir["relations"]) == 2


# --- T2 (F1): IR validation + theme normalisation ---

_VALID_IR = {
    "version": 1,
    "source": {"format": "excalidraw", "name": "x.excalidraw"},
    "frames": [],
    "elements": [
        {
            "id": "r1",
            "type": "rectangle",
            "bbox": {"x": 0, "y": 0, "w": 10, "h": 10},
            "label": None,
            "role": None,
        }
    ],
    "relations": [],
}


# @ac B-2 — a well-formed IR validates cleanly
def test_validate_ir_happy_path(tmp_path: Path, capsys) -> None:
    """B-2: a structurally valid IR → errors=0, exit 0."""
    from che_core.designer_ingest import validate_ir

    path = tmp_path / "ir.json"
    path.write_text(json.dumps(_VALID_IR), encoding="utf-8")

    rc = validate_ir(str(path))
    out = capsys.readouterr().out

    assert rc == 0, f"valid IR must return 0; got {rc}\nstdout={out!r}"
    assert "errors=0" in out, f"validator must print `errors=0`; got {out!r}"


# @ac B-2 — an IR missing `elements` is reported
def test_validate_ir_missing_elements(tmp_path: Path, capsys) -> None:
    """B-2: an IR without an `elements` array → exit 1, errors>=1 naming elements."""
    from che_core.designer_ingest import validate_ir

    path = tmp_path / "ir.json"
    path.write_text(
        json.dumps({"version": 1, "source": {"format": "excalidraw", "name": "x"}, "frames": [], "relations": []}),
        encoding="utf-8",
    )

    rc = validate_ir(str(path))
    out = capsys.readouterr().out

    assert rc == 1, f"invalid IR must return 1; got {rc}"
    match = re.search(r"errors=(\d+)", out)
    assert match is not None and int(match.group(1)) >= 1, f"errors count must be >=1; got {out!r}"
    assert "elements" in out, f"diagnostic must name the missing key; got {out!r}"


# @ac B-2 — a dangling relation endpoint is reported
def test_validate_ir_dangling_relation(tmp_path: Path, capsys) -> None:
    """B-2: a relation whose endpoint is not an element id → exit 1 naming the id."""
    from che_core.designer_ingest import validate_ir

    ir = dict(_VALID_IR)
    ir["relations"] = [{"from_id": "r1", "to_id": "ghost", "kind": "arrow"}]
    path = tmp_path / "ir.json"
    path.write_text(json.dumps(ir), encoding="utf-8")

    rc = validate_ir(str(path))
    out = capsys.readouterr().out

    assert rc == 1, f"dangling relation must return 1; got {rc}"
    assert "ghost" in out, f"diagnostic must name the dangling id; got {out!r}"


# @ac B-3 — proposed colours patch the canonical tokens.json
def test_ingest_theme_patches_colors(tmp_path: Path) -> None:
    """B-3: proposed primary colour lands in tokens.json; canonical keys stay."""
    from che_core.designer import run_init
    from che_core.designer_ingest import ingest_theme

    run_init(str(tmp_path), "test-session", "demo")
    proposed = tmp_path / "proposed.json"
    proposed.write_text(json.dumps({"colors": {"primary": "#3B82F6"}}), encoding="utf-8")

    rc = ingest_theme(str(tmp_path), "demo", str(proposed))

    assert rc == 0, f"ingest theme must return 0; got {rc}"
    tokens = json.loads((tmp_path / "design" / "tokens" / "tokens.json").read_text(encoding="utf-8"))
    assert tokens["colors"]["primary"] == "#3B82F6", f"primary must be patched; got {tokens['colors']!r}"
    assert "secondary" in tokens["colors"], "canonical colour keys must stay intact"


# @ac AB-2 — invalid hex is refused and tokens.json is left untouched (INV-1)
def test_ingest_theme_rejects_bad_hex(tmp_path: Path) -> None:
    """AB-2: a non-hex colour → CheError(THEME_INVALID) and no write."""
    from che_core.designer import run_init
    from che_core.designer_ingest import ingest_theme
    from che_core.diagnostics import CheError

    run_init(str(tmp_path), "test-session", "demo")
    tokens_path = tmp_path / "design" / "tokens" / "tokens.json"
    before = tokens_path.read_text(encoding="utf-8")
    proposed = tmp_path / "proposed.json"
    proposed.write_text(json.dumps({"colors": {"primary": "not-a-hex"}}), encoding="utf-8")

    with pytest.raises(CheError) as excinfo:
        ingest_theme(str(tmp_path), "demo", str(proposed))

    assert excinfo.value.code == "THEME_INVALID"
    assert tokens_path.read_text(encoding="utf-8") == before, "INV-1: tokens.json must not change on failure"


# --- T3 (F2): end-to-end render + orchestration skill ---


# @ac B-4 — init -> ingest theme -> render -> validate all succeed
def test_end_to_end_render(tmp_path: Path, capsys) -> None:
    """B-4: the F1 artefacts render into a valid DESIGN.md (render + validate exit 0)."""
    from che_core.designer import run_init, run_tokens_render, run_validate
    from che_core.designer_ingest import ingest_theme

    run_init(str(tmp_path), "test-session", "demo")
    proposed = tmp_path / "proposed.json"
    proposed.write_text(json.dumps({"colors": {"primary": "#3B82F6"}}), encoding="utf-8")
    ingest_theme(str(tmp_path), "demo", str(proposed))

    rc_render = run_tokens_render(str(tmp_path))
    capsys.readouterr()
    rc_validate = run_validate(str(tmp_path / "design" / "DESIGN.md"))
    out = capsys.readouterr().out

    assert rc_render == 0, f"render must exit 0; got {rc_render}"
    assert rc_validate == 0, f"DESIGN.md must validate; got {rc_validate}\n{out!r}"
    assert "errors=0" in out


# @ac B-5 — the orchestration skill documents the CLI contract
def test_skill_documents_cli_contract() -> None:
    """B-5: the skill exists, is frontmattered, and names the commands it orchestrates."""
    skill = Path(__file__).resolve().parent.parent / "skills" / "che-wireframe-to-ui" / "SKILL.md"

    assert skill.is_file(), f"missing skill at {skill}"
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---"), "skill must open with YAML frontmatter"
    assert "name:" in text and "description:" in text, "frontmatter needs name + description"
    assert "che designer ingest wireframe" in text, "skill must document the ingest command"
    assert "che designer tokens render" in text, "skill must document the render command"
