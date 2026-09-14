"""Tests for che_core.designer.run_tokens_render (T3 · F2 Single-source tokens + idempotent render).

Contract:
- B-3 (positive): running `tokens render <wt>` twice produces byte-identical DESIGN.md and tokens.styles.css (sha256 stable).
- B-3 (positive): tokens.styles.css is generated and contains --color-primary from tokens.json.
- B-3 (positive): DESIGN.md frontmatter is rewritten from tokens.json (single-source invariant R4).
- A-1 (assertive): missing design/ → sys.exit(2) before any file is written.
- A-2 (assertive): tokens.json without `colors` key → sys.exit(2).
- AB-5 (negative): tampered DESIGN.md frontmatter diverging from tokens.json → re-running tokens render
  restores consistency (single-source enforcement).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bootstrap_minimal_design_tree(wt: Path, *, primary: str = "#3B82F6") -> Path:
    """Create the minimal design tree (init) with one sub-product and a known tokens.json."""
    # init writes the tree.
    from che_core.designer import run_init

    assert run_init(str(wt), "sess-test-f2", "acme") == 0

    # Overwrite tokens.json with deterministic, valid colors for testing.
    tokens = {
        "$schema": "./tokens.schema.json",
        "version": 1,
        "sub_product": "acme",
        "created_at": "2026-09-14T20:00:00Z",
        "colors": {
            "primary": primary,
            "secondary": "#10B981",
            "surface": "#FFFFFF",
            "on_surface": "#0F172A",
        },
        "spacing": {"base": 4, "scale": [4, 8, 12, 16, 24, 32, 48, 64, 96, 128]},
        "rounded": {"sm": 2, "md": 8, "lg": 16, "xl": 24, "full": 9999},
        "typography": {
            "font_family_sans": "Inter",
            "font_family_serif": "Georgia",
            "scale": "1.250",
            "weights": [400, 500, 600, 700],
        },
        "elevation": {
            "e0": "none",
            "e1": "0 1px 2px rgba(0,0,0,.06)",
            "e2": "0 4px 12px rgba(0,0,0,.08)",
            "e3": "0 12px 32px rgba(0,0,0,.12)",
        },
        "components": {
            "button": {"radius": "md", "height": 40, "padding_x": 16, "padding_y": 8},
            "card": {"radius": "lg", "padding": 24, "elevation": "e1"},
        },
    }
    (wt / "design" / "tokens" / "tokens.json").write_text(json.dumps(tokens, indent=2), encoding="utf-8")
    return wt / "design" / "DESIGN.md"


# @ac B-3 — idempotency: two renders produce byte-identical files
def test_tokens_render_idempotent(tmp_path: Path) -> None:
    """Two consecutive `tokens render` runs must produce byte-identical DESIGN.md + tokens.styles.css (sha256 stable)."""
    from che_core.designer import run_tokens_render

    wt = tmp_path
    _bootstrap_minimal_design_tree(wt)

    rc1 = run_tokens_render(str(wt))
    assert rc1 == 0, f"first render must exit 0; got {rc1}"
    design_md = wt / "design" / "DESIGN.md"
    css = wt / "design" / "tokens" / "tokens.styles.css"
    sha_design_1 = _sha256(design_md)
    sha_css_1 = _sha256(css)

    rc2 = run_tokens_render(str(wt))
    assert rc2 == 0, f"second render must exit 0; got {rc2}"
    sha_design_2 = _sha256(design_md)
    sha_css_2 = _sha256(css)

    assert sha_design_1 == sha_design_2, (
        f"DESIGN.md must be byte-identical between renders (idempotency); run1={sha_design_1} run2={sha_design_2}"
    )
    assert sha_css_1 == sha_css_2, (
        f"tokens.styles.css must be byte-identical between renders; run1={sha_css_1} run2={sha_css_2}"
    )


# @ac B-3 — tokens.styles.css is generated and reflects tokens.json
def test_tokens_render_generates_css(tmp_path: Path) -> None:
    """tokens.styles.css must be created with --color-* CSS variables sourced from tokens.json."""
    from che_core.designer import run_tokens_render

    wt = tmp_path
    _bootstrap_minimal_design_tree(wt, primary="#FF00AA")

    rc = run_tokens_render(str(wt))
    assert rc == 0

    css = wt / "design" / "tokens" / "tokens.styles.css"
    assert css.is_file(), f"tokens.styles.css must exist at {css}"
    css_text = css.read_text(encoding="utf-8")
    # Each color token must appear as a CSS variable.
    assert "--color-primary: #FF00AA;" in css_text, f"primary color must propagate to CSS; got {css_text!r}"
    assert "--color-secondary: #10B981;" in css_text
    assert "--color-surface: #FFFFFF;" in css_text
    assert ":root" in css_text, "tokens.styles.css must be a :root { ... } declaration block"


# @ac B-3 — DESIGN.md frontmatter mirrors tokens.json (single-source invariant R4)
def test_tokens_render_syncs_frontmatter(tmp_path: Path) -> None:
    """Editing tokens.json colors and re-running render must rewrite DESIGN.md frontmatter to match (R4)."""
    from che_core.designer import run_tokens_render

    wt = tmp_path
    design_md = _bootstrap_minimal_design_tree(wt, primary="#3B82F6")
    run_tokens_render(str(wt))
    text_before = design_md.read_text(encoding="utf-8")
    assert "#3B82F6" in text_before, (
        f"primary #3B82F6 must appear in DESIGN.md after first render; got {text_before[:400]}"
    )

    # Mutate tokens.json primary to a different value.
    tokens_path = wt / "design" / "tokens" / "tokens.json"
    tokens = json.loads(tokens_path.read_text(encoding="utf-8"))
    tokens["colors"]["primary"] = "#C0FFEE"
    tokens_path.write_text(json.dumps(tokens, indent=2), encoding="utf-8")

    run_tokens_render(str(wt))
    text_after = design_md.read_text(encoding="utf-8")
    assert "#C0FFEE" in text_after, f"new primary #C0FFEE must appear after re-render; got {text_after[:400]}"
    assert "#3B82F6" not in text_after, (
        f"old primary #3B82F6 must NOT appear after re-render (single-source); got {text_after[:400]}"
    )


# @ac A-1 — design root missing → sys.exit(2) and zero side-effects
def test_tokens_render_a1_missing_design_root(tmp_path: Path) -> None:
    """A-1: design/ does not exist → sys.exit(2) before any file is written."""
    from che_core import designer as designer_mod

    wt = tmp_path  # no init ran
    with pytest.raises(SystemExit) as exc:
        designer_mod.run_tokens_render(str(wt))
    assert exc.value.code == 2, f"A-1 must exit 2; got {exc.value.code}"
    assert not (wt / "design").exists(), "design/ must not be created by render (init must run first)"


# @ac A-2 — tokens.json without `colors` → sys.exit(2)
def test_tokens_render_a2_tokens_missing_colors(tmp_path: Path) -> None:
    """A-2: tokens.json missing `colors` key → sys.exit(2)."""
    from che_core import designer as designer_mod

    wt = tmp_path
    _bootstrap_minimal_design_tree(wt)
    tokens_path = wt / "design" / "tokens" / "tokens.json"
    bad = {"version": 1, "sub_product": "acme", "no_colors_key": True}
    tokens_path.write_text(json.dumps(bad), encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        designer_mod.run_tokens_render(str(wt))
    assert exc.value.code == 2, f"A-2 must exit 2; got {exc.value.code}"


# @ac CLI — subparser is registered
def test_tokens_render_subcommand_registered() -> None:
    """`che designer tokens --help` and `che designer tokens render --help` exit 0 and document the wt arg."""
    r1 = subprocess.run(
        [sys.executable, "-m", "che_core.designer", "tokens", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r1.returncode == 0, f"`tokens --help` must exit 0; got {r1.returncode}\n{r1.stderr}"
    r2 = subprocess.run(
        [sys.executable, "-m", "che_core.designer", "tokens", "render", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r2.returncode == 0, f"`tokens render --help` must exit 0; got {r2.returncode}\n{r2.stderr}"
    assert "worktree_root" in r2.stdout, "`tokens render` must expose worktree_root positional arg"
