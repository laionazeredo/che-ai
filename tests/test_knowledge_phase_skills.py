"""Tests for the agent-facing knowledge layer: the skill, the command and the phase step.

Kept separate from ``test_knowledge.py`` (the engine) so the two layers ship as independent
reviewable units: this file asserts declarative content, not runtime behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest

WORKTREE = Path(__file__).resolve().parents[1]

PHASE_SKILLS = ["che-spec", "che-architect", "che-archeology", "che-act"]


def test_knowledge_skill_and_command_exist():
    # @ac B-7
    assert (WORKTREE / "skills" / "che-knowledge" / "SKILL.md").is_file()
    assert (WORKTREE / "commands" / "che-knowledge.md").is_file()


@pytest.mark.parametrize("skill", PHASE_SKILLS)
def test_phase_skills_carry_the_knowledge_step(skill):
    # @ac B-7
    text = (WORKTREE / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    assert "PROJECT KNOWLEDGE STEP" in text
    assert "che knowledge apply" in text
    assert "keep / alter / revert" in text
    assert "no-op" in text
