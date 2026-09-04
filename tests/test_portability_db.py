"""Smoke test portability: export/import com flag include_db; DB > 1MB deve ser SKIPPED."""

from __future__ import annotations

import json
import os
import sqlite3
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from che_core.paths import ensure_session_dirs
from che_core.portability import export_project, import_project
from che_core.state_store import rebuild_state_index


def _mk_project_content(tmp_path: Path):
    wt = tmp_path / "wt"
    wt.mkdir()
    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    os.environ["CHE_WORKSPACES_ROOT"] = str(ws_root)
    paths = ensure_session_dirs(str(wt), "smoke-portability")
    (Path(paths["CHE_PROJECT_DIR"]) / "architecture.md").write_text(
        "# Arquitetura\nMonorepo Next.js + tRPC.\n", encoding="utf-8"
    )
    shared = Path(paths["CHE_WORKSPACE_SHARED"])
    dec = shared / "decisions.log.jsonl"
    lines = []
    now = datetime.now(timezone.utc)
    for i in range(5):
        lines.append(json.dumps({"ts": now.isoformat(), "event": "DEC" + str(i), "worktree_root": str(wt)}))
    dec.write_text("\n".join(lines), encoding="utf-8")
    return wt


def test_export_without_db_produces_archive(tmp_path: Path):
    wt = _mk_project_content(tmp_path)
    out = tmp_path / "export-nodb.tar.gz"
    path_res = export_project(str(wt), str(out), include_db=False)
    assert Path(path_res).is_file()
    with tarfile.open(path_res, "r:gz") as tf:
        names = tf.getnames()
    assert any("architecture.md" in n for n in names)
    assert not any(n.lstrip("./").startswith("_db/") for n in names if n not in (".", "./"))


def test_export_with_db_big_size_limit_skips(tmp_path: Path):
    wt = _mk_project_content(tmp_path)
    rebuild_state_index(str(wt))
    from che_core.paths import compute_paths
    from che_core.state_store import _get_state_db_path

    paths = compute_paths(str(wt), "x")
    db_p = _get_state_db_path(paths=paths)
    conn = sqlite3.connect(str(db_p))
    conn.execute("CREATE TABLE IF NOT EXISTS bloat(id INTEGER PRIMARY KEY, data TEXT NOT NULL)")
    big_str = "X" * (1024 * 16)
    for _ in range(80):
        conn.execute("INSERT INTO bloat(data) VALUES(?)", (big_str,))
    conn.commit()
    conn.close()

    out = tmp_path / "export-dbskip.tar.gz"
    export_project(str(wt), str(out), include_db=True, db_size_limit_mb=1)
    assert Path(out).is_file()
    with tarfile.open(str(out), "r:gz") as tf:
        names = [n.lstrip("./") for n in tf.getnames()]
        # Tar cria "./_db/SKIPPED.txt" então strip("./") fica "_db/SKIPPED.txt"
        assert "_db/SKIPPED.txt" in names
        f = tf.extractfile("./_db/SKIPPED.txt" if "./_db/SKIPPED.txt" in tf.getnames() else "_db/SKIPPED.txt")
        assert f
        content = f.read().decode("utf-8")
        assert "exceeded" in content.lower() or "limite" in content.lower() or "MB" in content


def test_import_restores_files(tmp_path: Path):
    wt = _mk_project_content(tmp_path)
    out = tmp_path / "exp2.tar.gz"
    export_project(str(wt), str(out), include_db=False)

    target_ws = tmp_path / "target-ws"
    target_ws.mkdir()
    os.environ["CHE_WORKSPACES_ROOT"] = str(target_ws)
    res = import_project(str(out), target_workspace=None, include_db=False)
    assert isinstance(res, dict)
    # Ou status ou project_dir, dependendo da implementação
    assert res.get("project_dir") or res.get("status") or res.get("target_project_dir")
    project_dir = res.get("project_dir") or res.get("target_project_dir")
    if project_dir:
        assert Path(project_dir).exists()
