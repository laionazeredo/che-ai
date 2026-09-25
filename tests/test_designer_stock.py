"""Tests for che_core.designer.run_stock_add (T5 · F4 Stock asset — B-5 + AB-4 + R3).

Contract:
- B-5 (positive): an accepted image asset lands under design/assets/ and
  design/assets/CREDITS.md gains one entry with provider= / license= / source_url=.
- AB-4 (negative): an HTML/placeholder payload writes NOTHING and appends NO
  CREDITS entry; the pipeline advances to the next provider.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Minimal PNG magic bytes — enough for _is_real_image to classify as a real image.
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def test_stock_add_accepts_real_image(tmp_path: Path) -> None:
    """B-5: a real image is copied into design/assets/ and CREDITS.md gains one entry."""
    from che_core.designer import run_stock_add

    asset = tmp_path / "hero.png"
    asset.write_bytes(_PNG_BYTES)

    rc = run_stock_add(
        str(tmp_path),
        str(asset),
        "unsplash",
        "Unsplash License",
        "https://images.unsplash.com/photo-test",
    )
    assert rc == 0

    dest = tmp_path / "design" / "assets" / "hero.png"
    credits = tmp_path / "design" / "assets" / "CREDITS.md"
    assert dest.is_file(), f"asset must be copied to {dest}"
    assert credits.is_file(), f"CREDITS.md must be created at {credits}"

    text = credits.read_text(encoding="utf-8")
    assert "provider=unsplash" in text
    assert "license=Unsplash License" in text
    assert "source_url=https://images.unsplash.com/photo-test" in text
    assert text.count("provider=") == 1, f"exactly one CREDITS entry expected; got:\n{text}"


def test_stock_add_rejects_html_placeholder(tmp_path: Path) -> None:
    """AB-4: an HTML/403 payload writes NOTHING and appends NO CREDITS entry."""
    from che_core.designer import run_stock_add
    from che_core.diagnostics import CheError

    asset = tmp_path / "fake.png"
    asset.write_bytes(b"<!DOCTYPE html><html><body>403 Forbidden</body></html>")

    with pytest.raises(CheError) as exc_info:
        run_stock_add(
            str(tmp_path),
            str(asset),
            "unsplash",
            "Unsplash License",
            "https://example.com/forbidden",
        )
    assert exc_info.value.code == "ASSET_NOT_AN_IMAGE"
    assert exc_info.value.exit_code != 0, "placeholder payload must abort with non-zero exit"

    assets_dir = tmp_path / "design" / "assets"
    assert not (assets_dir / "fake.png").exists(), "placeholder must NOT be written under design/assets/"
    assert not (assets_dir / "CREDITS.md").exists(), "no CREDITS.md entry may be appended for a placeholder"


def test_stock_add_subcommand_registered() -> None:
    """`che designer stock add --help` must exit 0 and document the flags."""
    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "che_core.designer", "stock", "add", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, "stock add --help must exit 0"
    for flag in ("--provider", "--license", "--source-url"):
        assert flag in result.stdout, f"stock add parser must expose {flag}"


def test_stock_add_requires_provenance_fields(tmp_path: Path) -> None:
    """run_stock_add rejects empty provider/license/source_url (precondition)."""
    from che_core.designer import run_stock_add
    from che_core.diagnostics import CheError

    asset = tmp_path / "hero.png"
    asset.write_bytes(_PNG_BYTES)

    with pytest.raises(CheError) as exc_info:
        run_stock_add(str(tmp_path), str(asset), "", "CC0", "https://example.com")
    assert exc_info.value.code == "MISSING_ASSET_METADATA"
    assert exc_info.value.exit_code != 0
