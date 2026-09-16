"""Tests for the OpenPencil connector + backend contract (T7 · F6 — B-7 + R7).

Contract:
- B-7 (positive): the 3 missing references exist; every `references/*.md` path
  cited by skills/che-social-ui-designer/SKILL.md resolves on disk; the
  OpenPencil save_file/export_svg targets resolve under <wt>/design/.
"""

from __future__ import annotations

import re
from pathlib import Path

_CHE_HOME = Path(__file__).resolve().parent.parent
_SKILL = _CHE_HOME / "skills" / "che-social-ui-designer" / "SKILL.md"

_REF_RE = re.compile(r"references/[a-zA-Z0-9_/.-]+\.md")

_THREE_REFS = (
    _CHE_HOME / "skills" / "che-social-ui-designer" / "references" / "DESIGN_BACKEND_CONTRACT.md",
    _CHE_HOME / "skills" / "che-social-ui-designer" / "references" / "backends" / "OPENPENCIL.md",
    _CHE_HOME / "skills" / "che-social-ui-designer" / "references" / "backends" / "FIGMA.md",
)


def test_three_missing_references_exist() -> None:
    for ref in _THREE_REFS:
        assert ref.is_file(), f"missing reference: {ref.relative_to(_CHE_HOME)}"


def test_skill_cited_references_all_resolve() -> None:
    """Every `references/*.md` path cited by SKILL.md must resolve on disk.

    Paths are cited relative to the SKILL.md's own directory
    (`skills/che-social-ui-designer/`), not the worktree root.
    """
    skill_dir = _SKILL.parent
    text = _SKILL.read_text(encoding="utf-8")
    refs = set(_REF_RE.findall(text))
    assert refs, "SKILL.md must cite at least one references/*.md path"

    missing = [r for r in sorted(refs) if not (skill_dir / r).is_file()]
    assert missing == [], f"missing references cited by SKILL.md: {missing!r}"


def test_openpencil_connector_targets_under_design() -> None:
    """The OpenPencil connector config must point save/export targets under <wt>/design/."""
    connector = _CHE_HOME / "domains" / "ux" / "connectors" / "openpencil.config.md"
    assert connector.is_file(), "openpencil.config.md must exist"

    text = connector.read_text(encoding="utf-8")
    assert "design/<sub_product>/source/home.op" in text, "save_file target must be under design/<sub_product>/"
    assert "design/<sub_product>/exports/" in text, "export_svg target must be under design/<sub_product>/"
