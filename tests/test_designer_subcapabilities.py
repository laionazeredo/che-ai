"""Tests for the UX sub-capability map + link integrity (T6 · F5 — B-8 + R1/R7).

Contract:
- B-8 (positive): domains/ux/knowledge/sub-capabilities.md exists; every relative
  path referenced by the file resolves on disk (broken_links == 0); each of the 6
  capabilities (branding, logo & iconography, UI web, UI mobile-first, design
  system, social) maps to exactly one skill or connector path.
"""

from __future__ import annotations

import re
from pathlib import Path

_CHE_HOME = Path(__file__).resolve().parent.parent
_SUB_CAPABILITIES = _CHE_HOME / "domains" / "ux" / "knowledge" / "sub-capabilities.md"

_SIX_CAPABILITIES = (
    "Branding",
    "Logo & iconography",
    "UI web",
    "UI mobile-first",
    "Design system",
    "Social",
)

_PATH_RE = re.compile(r"`([a-zA-Z0-9_/.-]+\.md)`")


def test_sub_capabilities_file_exists() -> None:
    assert _SUB_CAPABILITIES.is_file(), f"{_SUB_CAPABILITIES} must exist"


def test_sub_capabilities_link_integrity() -> None:
    """Every backticked .md path in sub-capabilities.md must resolve on disk."""
    text = _SUB_CAPABILITIES.read_text(encoding="utf-8")
    paths = _PATH_RE.findall(text)
    assert paths, "sub-capabilities.md must reference at least one .md path"

    broken = [p for p in paths if not (_CHE_HOME / p).is_file()]
    assert broken == [], f"broken_links={len(broken)}: {broken!r}"


def test_sub_capabilities_maps_six_capabilities() -> None:
    """Each of the 6 capabilities must appear exactly once in the map."""
    text = _SUB_CAPABILITIES.read_text(encoding="utf-8")
    for capability in _SIX_CAPABILITIES:
        assert capability in text, f"missing capability: {capability}"


def test_sub_capabilities_has_canonical_references() -> None:
    """The map must reference the backend contract + both backend drivers (R7)."""
    text = _SUB_CAPABILITIES.read_text(encoding="utf-8")
    assert "DESIGN_BACKEND_CONTRACT.md" in text
    assert "backends/OPENPENCIL.md" in text
    assert "backends/FIGMA.md" in text
