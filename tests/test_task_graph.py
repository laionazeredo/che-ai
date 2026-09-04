"""Smoke test para task_graph: parse, DAG build, waves, summary."""

from __future__ import annotations

import os
from pathlib import Path

from che_core.paths import ensure_session_dirs
from che_core.task_graph import build_dag, kahn_waves, parse_task_graph, summarize_graph


def _setup(tmp_path: Path):
    """Cria worktree fake + cria CHE_WORKSPACE_SHARED com task_graph.md e envelopes."""
    wt = tmp_path / "wt"
    wt.mkdir()
    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    os.environ["CHE_WORKSPACES_ROOT"] = str(ws_root)
    paths = ensure_session_dirs(str(wt), "tg-smoke")
    shared = Path(paths["CHE_WORKSPACE_SHARED"])
    return wt, shared


def test_parse_empty_task_graph(tmp_path: Path):
    wt, shared = _setup(tmp_path)
    # não cria task_graph.md
    result = parse_task_graph(str(wt))
    assert isinstance(result["tasks"], dict)
    assert result["tasks"] == {}


def test_parse_task_graph_with_domain_col(tmp_path: Path):
    wt, shared = _setup(tmp_path)
    (shared / "task_graph.md").write_text(
        """
# Tasks

| ID | Title | Depends on | Status | Domain | DONE |
|---|---|---|---|---|---|
| T1 | UX coisa |  | TODO | ux | entrega figma |
| T2 | Eng coisa | T1 | TODO | engineering | codigo roda |
""".strip(),
        encoding="utf-8",
    )
    tasks_root = shared / "tasks"
    (tasks_root / "T1").mkdir(parents=True, exist_ok=True)
    (tasks_root / "T1" / "envelope.md").write_text("foo envelope", encoding="utf-8")
    (tasks_root / "T2").mkdir(parents=True, exist_ok=True)
    (tasks_root / "T2" / "envelope.md").write_text("bar envelope", encoding="utf-8")
    result = parse_task_graph(str(wt))
    ids = list(result["tasks"].keys())
    assert "T1" in ids and "T2" in ids
    assert result["tasks"]["T1"]["domain"] == "ux"
    assert result["tasks"]["T2"]["domain"] == "engineering"


def test_parse_task_graph_legacy_no_domain_col_defaults_engineering(tmp_path: Path):
    wt, shared = _setup(tmp_path)
    (shared / "task_graph.md").write_text(
        """
# Tasks

| ID | Title | Depends on | Status | DONE |
|---|---|---|---|---|
| T1 | coisa |  | TODO | x |
""".strip(),
        encoding="utf-8",
    )
    tasks_root = shared / "tasks"
    (tasks_root / "T1").mkdir(parents=True, exist_ok=True)
    (tasks_root / "T1" / "envelope.md").write_text("e", encoding="utf-8")
    result = parse_task_graph(str(wt))
    assert result["tasks"]["T1"]["domain"] == "engineering"


def test_build_dag_and_kahn_waves_simple(tmp_path: Path):
    wt, shared = _setup(tmp_path)
    (shared / "task_graph.md").write_text(
        """
| ID | Title | Depends on | Status | Domain | DONE |
|---|---|---|---|---|---|
| T1 | 1 |  | TODO | engineering | |
| T2 | 2 | T1 | TODO | engineering | |
| T3 | 3 | T1 | TODO | engineering | |
| T4 | 4 | T2, T3 | TODO | engineering | |
""".strip(),
        encoding="utf-8",
    )
    for t in ("T1", "T2", "T3", "T4"):
        p = shared / "tasks" / t
        p.mkdir(parents=True, exist_ok=True)
        (p / "envelope.md").write_text("e", encoding="utf-8")
    graph = parse_task_graph(str(wt))
    assert len(graph["tasks"]) == 4
    fwd, rev = build_dag(graph)
    assert "T2" in fwd.get("T1", [])
    assert "T3" in fwd.get("T1", [])
    assert "T4" in fwd.get("T2", [])
    assert "T4" in fwd.get("T3", [])
    waves = kahn_waves(graph)
    assert len(waves) >= 2
    first_tids = set(waves[0]["tids"])
    assert "T1" in first_tids


def test_summarize_empty(tmp_path: Path):
    wt, shared = _setup(tmp_path)
    graph = parse_task_graph(str(wt))
    s = summarize_graph(graph)
    assert "total" in s
    assert s["total"] == 0
    assert "waves" in s
    assert isinstance(s["waves"], list)
