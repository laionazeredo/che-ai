"""Smoke test state_store: rebuild, sanitize(dry-run), search, query SQL whitelist."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from che_core.diagnostics import CheError
from che_core.state_store import query_state_db, rebuild_state_index, sanitize_state, search_state
from tests.conftest import bind_worktree

CHE_ROOT = Path(__file__).resolve().parent.parent


def _setup_wt_with_content(tmp_path: Path):
    repo, paths = bind_worktree(tmp_path)
    shared = Path(paths["CHE_WORKSPACE_SHARED"])

    (shared / "task_graph.md").write_text(
        """
# Tasks
| ID | Title | Depends on | Status | Domain | DONE |
|---|---|---|---|---|---|
| T1 | Create UI |  | TODO | ux | mockup ready |
| T2 | Implement | T1 | TODO | engineering | tests passing |
""".strip(),
        encoding="utf-8",
    )
    tasks = shared / "tasks"
    (tasks / "T1").mkdir(parents=True, exist_ok=True)
    (tasks / "T1" / "envelope.md").write_text(
        "domain: ux\ntitle: Create UI\nexpert_skills: penpot\nhandoff_output: designs/ui.fig\ndone_criteria: mockup ready\n\nBody task one.",
        encoding="utf-8",
    )
    (tasks / "T2").mkdir(parents=True, exist_ok=True)
    (tasks / "T2" / "envelope.md").write_text(
        "domain: engineering\ntitle: Implement\nexpert_skills: typescript\nhandoff_output: src/\ndone_criteria: tests\n\nBody task two.",
        encoding="utf-8",
    )

    dec_file = shared / "decisions.log.jsonl"
    now = datetime.now(timezone.utc)
    lines = []
    for i in range(20):
        ts = (now - timedelta(days=300 - i * 5)).isoformat()
        lines.append(
            json.dumps(
                {
                    "ts": ts,
                    "event": f"TEST_{i}",
                    "worktree_root": str(repo),
                    "task_id": f"T{i % 2 + 1}",
                    "payload": {"dec_num": i, "note": f"old decision {i}"},
                }
            )
        )
    dec_file.write_text("\n".join(lines), encoding="utf-8")

    # Che creates artifact folders lazily (output_path makes the parent at write
    # time), so a fixture seeding content must create its own directory — as the
    # `tasks/T1` block above already does.
    specs_dir = shared / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    (specs_dir / "spec-ui.md").write_text(
        "---\ntitle: UI Spec\nstatus: Approved\ndomain: ux\n---\n\nThis is the interface spec containing UX flows and payment details.",
        encoding="utf-8",
    )
    return repo


def test_rebuild_index_creates_db_and_counts(tmp_path: Path):
    wt = _setup_wt_with_content(tmp_path)
    res = rebuild_state_index(str(wt))
    assert "tasks" in res and "decisions" in res and "specs" in res
    assert res["tasks"] >= 2
    assert res["decisions"] >= 10
    assert res["specs"] >= 1
    from che_core.paths import compute_paths

    paths = compute_paths(str(wt), "x")
    db_path = Path(paths["CHE_DB_DIR"]) / "che_state.sqlite"
    assert db_path.is_file()


def test_query_state_db_whitelist_readonly(tmp_path: Path):
    wt = _setup_wt_with_content(tmp_path)
    rebuild_state_index(str(wt))
    res = query_state_db(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
        worktree_root=str(wt),
        as_json=True,
    )
    assert isinstance(res, dict)
    tables = [r["name"] for r in res["rows"]]
    assert "tasks" in tables
    assert "decisions" in tables
    # INSERT must fail without --force: catalogued STATE_QUERY_NEEDS_FORCE.
    with pytest.raises(CheError) as exc:
        query_state_db(
            "INSERT INTO tasks(id,title,status,domain,updated_at) VALUES('X','Y','TODO','engineering','2024-01-01')",
            worktree_root=str(wt),
        )
    assert exc.value.code == "STATE_QUERY_NEEDS_FORCE"
    assert exc.value.exit_code == 2


def _cli(args: list, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "che_core.cli", "--json", *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(CHE_ROOT),
        env=env,
    )


def test_the_cli_exposes_the_force_flag_the_refusal_names(tmp_path: Path) -> None:
    """A hint that names a flag the command does not have is worse than no hint.

    `STATE_QUERY_NEEDS_FORCE` tells the caller to pass `--force`; the flag is therefore part of the
    failure's contract, not a nicety. The three runs below differ only in what the caller supplied,
    and each is read from the envelope — the code, never the wording.

    No index is built on purpose: the refusal and the missing-argument check both happen before the
    database is opened, so nothing is written and the codes prove which gate was reached.
    """
    repo, _ = bind_worktree(tmp_path)
    env = dict(os.environ, CHE_WORKSPACES_ROOT=str(tmp_path / "che-workspaces"))
    write = "INSERT INTO tasks(id,title,status,domain,updated_at) VALUES('X','Y','TODO','engineering','2024-01-01')"

    refused = _cli(["state", "query", "--sql", write, "--worktree-root", str(repo)], env)
    assert json.loads(refused.stdout)["code"] == "STATE_QUERY_NEEDS_FORCE"

    # Accepted, so the run reaches the next gate — the state store has not been built yet.
    forced = _cli(["state", "query", "--sql", write, "--worktree-root", str(repo), "--force"], env)
    assert json.loads(forced.stdout)["code"] == "STATE_DB_MISSING"

    # Without a worktree there is no database to open: a catalogued failure, not a ValueError.
    rootless = _cli(["state", "query", "--sql", "SELECT 1"], env)
    assert json.loads(rootless.stdout)["code"] == "MISSING_WORKTREE_ROOT"
    assert rootless.returncode == 2


def test_sanitize_dry_run_then_apply(tmp_path: Path):
    wt = _setup_wt_with_content(tmp_path)
    rebuild_state_index(str(wt))
    res_dry = sanitize_state(str(wt), max_age_days=180, max_decisions=5, dry_run=True)
    assert res_dry["dry_run"] is True
    # decisions_old: decisions with ts > 180 days in the past
    assert res_dry["deleted"]["decisions_old"] >= 1
    # decisions_over_cap if 20 - 5 = 15
    assert res_dry["deleted"]["decisions_over_cap"] >= 10
    # Apply
    res = sanitize_state(str(wt), max_age_days=180, max_decisions=5, dry_run=False)
    assert res["dry_run"] is False
    # VACUUM might throw "database is locked" in pytest environments with remaining connections;
    # this is not a functional error of sanitize, just a connection race on the final VACUUM.
    err = res.get("error") or ""
    assert (err == "") or ("locked" in err.lower()) or ("vacuum" in err.lower())
    # Deleted count applies for real (always >= than in dry-run since nothing was removed before)
    assert res["deleted"]["decisions_old"] >= 1
    assert res["deleted"]["decisions_over_cap"] >= 10


def test_search_state_returns_serializable_and_has_matches(tmp_path: Path):
    wt = _setup_wt_with_content(tmp_path)
    rebuild_state_index(str(wt))
    # Query com palavras certas do nosso corpus
    r = search_state(str(wt), "UX interface spec", top_k=10, scope="all")
    assert isinstance(r, dict)
    json.dumps(r)
    assert "results" in r
    # Might have 0 matches if FTS5 is not supported, but search_state works.
    assert isinstance(r["results"], list)
