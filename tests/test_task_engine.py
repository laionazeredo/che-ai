"""Smoke test para task_engine: list/show/set-status. Sem task_graph não crasha."""
from __future__ import annotations

import json
import os
from pathlib import Path

from che_core.task_engine import list_tasks, set_status_task, show_task


def _mk_worktree(tmp_path: Path):
    wt = tmp_path / "wt"
    wt.mkdir()
    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    os.environ["CHE_WORKSPACES_ROOT"] = str(ws_root)
    return wt


def test_list_tasks_empty_returns_serializable(tmp_path: Path):
    wt = _mk_worktree(tmp_path)
    result = list_tasks(str(wt))
    # list_tasks retorna hoje lista de dicts; garantimos serializável.
    json.dumps(result)
    # Se é lista, aceitamos; dict também
    assert isinstance(result, (list, dict))


def test_show_task_missing_returns_dict(tmp_path: Path):
    wt = _mk_worktree(tmp_path)
    r = show_task(str(wt), "T-NOEXIST")
    assert isinstance(r, dict)
    json.dumps(r)


def test_set_status_task_nonexistent_no_crash(tmp_path: Path):
    wt = _mk_worktree(tmp_path)
    r = set_status_task(str(wt), "T-X", "DONE", session_id="smoke1", reason="test")
    assert isinstance(r, dict)
    json.dumps(r)
