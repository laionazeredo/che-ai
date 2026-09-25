"""Contract tests for the hook failure envelope.

A hook must never block the tool call, so a crash still answers `allow`. That safety net has one
cost: `allow` is also what a hook says when it ran and found nothing wrong. These tests pin the
only thing that keeps the two apart — a crashed hook names itself as crashed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from che_core.hooks import HOOK_FAILURE_MARKER, hook_failure

CHE_ROOT = Path(__file__).resolve().parent.parent
HOOK_SCRIPTS = sorted((CHE_ROOT / "hooks").glob("*.py"))


def test_a_hook_failure_is_marked_and_still_allows() -> None:
    envelope = hook_failure(ValueError("boom"))

    assert envelope["decision"] == "allow", "a hook crash must never block the tool call"
    assert envelope["che_hook_failed"] is True
    assert envelope["reason"].startswith(HOOK_FAILURE_MARKER)
    assert "ValueError" in envelope["reason"]
    assert "boom" in envelope["additionalContext"]


def test_there_is_a_hook_to_test() -> None:
    assert HOOK_SCRIPTS, "the adapters install these scripts; none found means the layout moved"


@pytest.mark.parametrize("script", HOOK_SCRIPTS, ids=lambda path: path.name)
def test_every_hook_script_reports_a_crash_instead_of_a_silent_allow(script: Path) -> None:
    """Unreadable stdin is the cheapest crash to provoke, and the one that used to look like a pass."""
    environ = dict(os.environ, CHE_HOME=str(CHE_ROOT))

    proc = subprocess.run(
        [sys.executable, str(script)],
        input="not json at all",
        capture_output=True,
        text=True,
        check=False,
        env=environ,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["che_hook_failed"] is True
    assert payload["decision"] == "allow"
    assert HOOK_FAILURE_MARKER in payload["reason"]
