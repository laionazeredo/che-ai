"""Tests for che_core.designer.run_validate (T2 · F1 Validator — B-2 + AB-2/3/4 + A-3).

Contract:
- B-2 (positive): DESIGN.md with frontmatter + 8 canonical sections in order → errors=0, exit 0.
- AB-2 (negative): duplicate `## Colors` → exit 1, errors>=1.
- AB-3 (negative): missing one canonical section → exit 1, errors>=1.
- AB-4 (negative / A-3): no YAML frontmatter or wrong delimiter count → exit 1.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CANONICAL_SECTIONS = [
    "Overview",
    "Colors",
    "Typography",
    "Layout",
    "Elevation & Depth",
    "Shapes",
    "Components",
    "Do's and Don'ts",
]


def _build_minimal_design_md(tmp_path: Path, *, duplicate_colors: bool = False, missing: str | None = None) -> Path:
    """Build a minimal-but-valid DESIGN.md per Stitch spec (used as test fixture)."""
    md = tmp_path / "DESIGN.md"
    fm_delim = "---\n"
    body_parts = [fm_delim, "version: 1\n", "name: acme\n", "spec: stitch-design-md\n", fm_delim, "\n"]
    body_parts.append("# DESIGN.md — acme\n\n")
    for sec in CANONICAL_SECTIONS:
        if missing and sec == missing:
            continue
        body_parts.append(f"## {sec}\n\nPlaceholder body.\n\n")
        if duplicate_colors and sec == "Colors":
            # Add a second `## Colors` further down to trigger duplicate-section failure.
            body_parts.append("## Colors\n\nDuplicate body.\n\n")
    md.write_text("".join(body_parts), encoding="utf-8")
    return md


# @ac B-2 — happy path: 8 sections + frontmatter
def test_validate_happy_path(tmp_path: Path, capsys) -> None:
    """B-2: frontmatter + 8 canonical sections in order → errors=0, exit 0."""
    from che_core.designer import run_validate

    md = _build_minimal_design_md(tmp_path)
    rc = run_validate(str(md))
    captured = capsys.readouterr()
    out = captured.out

    assert rc == 0, f"validator must return 0 on happy path; got {rc}\nstdout={out!r}"
    # Contract: stdout contains `errors=0` and lists the 8 canonical ## sections in order.
    assert "errors=0" in out, f"validator must print `errors=0`; got {out!r}"
    last_positions = [out.rfind(f"## {sec}") for sec in CANONICAL_SECTIONS]
    assert all(p >= 0 for p in last_positions), (
        f"all 8 sections must appear in stdout; got positions={last_positions}\nout={out!r}"
    )
    assert last_positions == sorted(last_positions), (
        f"8 canonical sections must appear in canonical order; positions={last_positions}"
    )


# @ac AB-2 — duplicate section header
def test_validate_duplicate_colors_section(tmp_path: Path, capsys) -> None:
    """AB-2: duplicate `## Colors` → exit 1, errors>=1."""
    from che_core.designer import run_validate

    md = _build_minimal_design_md(tmp_path, duplicate_colors=True)
    rc = run_validate(str(md))
    captured = capsys.readouterr()
    out = captured.out

    assert rc != 0, f"validator must exit non-zero on duplicate section; got {rc}"
    # Match either `errors=N` (N>=1) or `errors>0` (fuzzy).
    m = re.search(r"errors=(\d+)", out)
    assert m is not None and int(m.group(1)) >= 1, f"errors count must be >=1; got stdout={out!r}"
    assert "duplicate" in out.lower() or "Colors" in out, (
        f"validator must name the offending section (Colors) in the diagnostic; got {out!r}"
    )


# @ac AB-3 — missing canonical section
def test_validate_missing_section(tmp_path: Path, capsys) -> None:
    """AB-3: drop one canonical section (e.g. Shapes) → exit 1, errors>=1."""
    from che_core.designer import run_validate

    md = _build_minimal_design_md(tmp_path, missing="Shapes")
    rc = run_validate(str(md))
    captured = capsys.readouterr()
    out = captured.out

    assert rc != 0, f"validator must exit non-zero on missing section; got {rc}"
    m = re.search(r"errors=(\d+)", out)
    assert m is not None and int(m.group(1)) >= 1, f"errors count must be >=1; got stdout={out!r}"
    assert "Shapes" in out, f"validator must name the missing section (Shapes) in diagnostic; got {out!r}"


# @ac AB-4 / A-3 — frontmatter delimiter count must be exactly 2
def test_validate_no_frontmatter(tmp_path: Path, capsys) -> None:
    """AB-4 / A-3: frontmatter delimiter count must be exactly 2 lines (open + close)."""
    from che_core.designer import run_validate

    md = tmp_path / "DESIGN.md"
    # Only one `---` delimiter at top, no closing one → A-3 violation.
    md.write_text("---\nversion: 1\n# Title\nbody without frontmatter close\n", encoding="utf-8")

    rc = run_validate(str(md))
    captured = capsys.readouterr()
    out = captured.out

    assert rc != 0, f"validator must exit non-zero when frontmatter delimiter count != 2; got {rc}"
    m = re.search(r"errors=(\d+)", out)
    assert m is not None and int(m.group(1)) >= 1, f"errors count must be >=1; got stdout={out!r}"
    # Diagnostic must mention the frontmatter (A-3 is about delimiter count).
    assert "frontmatter" in out.lower() or "delimiter" in out.lower() or "---" in out, (
        f"validator must explain the A-3 violation; got {out!r}"
    )


# @ac CLI — `che designer validate` is registered and runs end-to-end via subprocess
def test_validate_subcommand_registered_and_runs(tmp_path: Path) -> None:
    """CLI smoke: `che designer validate <md>` exits 0 on the happy path fixture."""
    md = _build_minimal_design_md(tmp_path)
    result = subprocess_run_validate(str(md))
    assert result.returncode == 0, (
        f"`che designer validate <happy.md>` must exit 0; got {result.returncode}\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    assert "errors=0" in result.stdout


def subprocess_run_validate(design_md_path: str):
    """Thin wrapper so the test reads naturally."""
    import subprocess

    return subprocess.run(
        [sys.executable, "-m", "che_core.designer", "validate", design_md_path],
        capture_output=True,
        text=True,
        check=False,
    )
