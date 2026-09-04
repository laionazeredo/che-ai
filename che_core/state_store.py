import json
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from che_core.paths import compute_paths
from che_core.task_graph import parse_task_graph


def _get_state_db_path(worktree_root: Optional[str] = None, paths: Optional[Dict[str, str]] = None) -> Path:
    if paths is None:
        if worktree_root is None:
            raise ValueError("worktree_root or paths must be provided")
        paths = compute_paths(worktree_root, "state-store-fallback")
    return Path(paths["CHE_PROJECT_DIR"]) / "che_state.sqlite"


def _connect(db_path: Path, read_only: bool = False) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if read_only:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'TODO',
            domain TEXT NOT NULL DEFAULT 'engineering',
            depends_on TEXT NOT NULL DEFAULT '',
            envelope_path TEXT UNIQUE,
            envelope_body TEXT NOT NULL DEFAULT '',
            expert_skills TEXT NOT NULL DEFAULT '',
            handoff_output TEXT NOT NULL DEFAULT '',
            done_criteria TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS task_dependencies (
            child_id TEXT NOT NULL,
            parent_id TEXT NOT NULL,
            PRIMARY KEY (child_id, parent_id),
            FOREIGN KEY (child_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_id) REFERENCES tasks(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            event TEXT NOT NULL,
            worktree_root TEXT NOT NULL,
            task_id TEXT,
            spec_id TEXT,
            session_id TEXT,
            payload TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS specs (
            spec_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'Draft',
            domain TEXT NOT NULL DEFAULT 'engineering',
            frontmatter_json TEXT NOT NULL DEFAULT '{}',
            body TEXT NOT NULL DEFAULT '',
            path TEXT UNIQUE,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS bindings (
            session_id TEXT PRIMARY KEY,
            ts TEXT NOT NULL,
            status TEXT NOT NULL,
            worktree_root TEXT NOT NULL,
            flags_json TEXT NOT NULL DEFAULT '{}',
            data_json TEXT NOT NULL DEFAULT '{}',
            session_dir TEXT
        );
        """
    )
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts USING fts5(title, envelope_body, content=tasks, content_rowid=rowid)"
        )
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS decisions_fts USING fts5(payload, content=decisions, content_rowid=id)"
        )
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS specs_fts USING fts5(body, content=specs, content_rowid=rowid)"
        )
    except sqlite3.OperationalError:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_title ON tasks(title)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_decisions_ts ON decisions(ts)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_specs_domain ON specs(domain)")


def _parse_spec_frontmatter(path: Path, spec_id: str, body: str) -> Tuple[str, str, Dict[str, Any]]:
    domain = "engineering"
    status = "Draft"
    fm: Dict[str, Any] = {}

    if body.startswith("---"):
        parts = body.split("---", 2)
        if len(parts) >= 3:
            fm_block = parts[1]
            for line in fm_block.splitlines():
                line = line.strip()
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip().lower()
                    v = v.strip().strip("'\"")
                    fm[k] = v
                    if k == "domain":
                        domain = v.lower() if v else "engineering"
                    elif k == "status":
                        status = v
    return status, domain, fm


def rebuild_state_index(worktree_root: str) -> Dict[str, Any]:
    paths = compute_paths(worktree_root, "state-rebuild")
    db_path = _get_state_db_path(paths=paths)
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        counts: Dict[str, int] = {
            "tasks": 0,
            "task_dependencies": 0,
            "decisions": 0,
            "specs": 0,
            "bindings": 0,
            "errors": 0,
        }
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        with conn:
            graph = parse_task_graph(worktree_root, session_id="state-rebuild")
            for tid, task in graph["tasks"].items():
                envelope = task.get("envelope", {})
                try:
                    conn.execute(
                        """INSERT INTO tasks(id,title,status,domain,depends_on,envelope_path,envelope_body,expert_skills,handoff_output,done_criteria,updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?)
                           ON CONFLICT(id) DO UPDATE SET
                             title=excluded.title,
                             status=excluded.status,
                             domain=excluded.domain,
                             depends_on=excluded.depends_on,
                             envelope_path=excluded.envelope_path,
                             envelope_body=excluded.envelope_body,
                             expert_skills=excluded.expert_skills,
                             handoff_output=excluded.handoff_output,
                             done_criteria=excluded.done_criteria,
                             updated_at=excluded.updated_at""",
                        (
                            tid,
                            task.get("title", ""),
                            task.get("status", "TODO"),
                            task.get("domain", "engineering"),
                            json.dumps(task.get("depends_on", []), ensure_ascii=False),
                            task.get("envelope_path"),
                            envelope.get("raw", ""),
                            json.dumps(envelope.get("expert_skills", []), ensure_ascii=False),
                            json.dumps(envelope.get("handoff_output", []), ensure_ascii=False),
                            task.get("done_criteria", ""),
                            now_iso,
                        ),
                    )
                    counts["tasks"] += 1
                    for dep in task.get("depends_on", []):
                        conn.execute(
                            "INSERT OR IGNORE INTO task_dependencies(child_id,parent_id) VALUES(?,?)",
                            (tid, dep),
                        )
                        counts["task_dependencies"] += 1
                except Exception as exc:
                    print(f"[state-store rebuild] task {tid} error: {exc}", file=sys.stderr)
                    counts["errors"] += 1

            decisions_path = Path(paths["CHE_WORKSPACE_SHARED"]) / "decisions.log.jsonl"
            if decisions_path.exists():
                try:
                    conn.execute("DELETE FROM decisions WHERE worktree_root = ?", (worktree_root,))
                    with open(decisions_path, "r", encoding="utf-8") as f:
                        for ln in f:
                            ln = ln.strip()
                            if not ln:
                                continue
                            try:
                                entry = json.loads(ln)
                                task_id = None
                                spec_id = None
                                session_id = None
                                payload_raw = ln
                                data = entry.get("data") or entry.get("payload") or {}
                                if isinstance(data, dict):
                                    task_id = data.get("task_id") or data.get("active_task")
                                    spec_id = entry.get("spec_id")
                                    session_id = entry.get("session_id")
                                    payload_raw = json.dumps(data, ensure_ascii=False)
                                conn.execute(
                                    "INSERT INTO decisions(ts,event,worktree_root,task_id,spec_id,session_id,payload) VALUES(?,?,?,?,?,?,?)",
                                    (
                                        entry.get("ts", now_iso),
                                        entry.get("event", "UNKNOWN"),
                                        worktree_root,
                                        task_id,
                                        spec_id,
                                        session_id,
                                        payload_raw,
                                    ),
                                )
                                counts["decisions"] += 1
                            except Exception:
                                counts["errors"] += 1
                except Exception as exc:
                    print(f"[state-store rebuild] decisions error: {exc}", file=sys.stderr)
                    counts["errors"] += 1

            specs_root = Path(paths["CHE_WORKSPACE_SHARED"]) / "specs"
            if specs_root.is_dir():
                conn.execute("DELETE FROM specs")
                for md_file in specs_root.rglob("*.md"):
                    try:
                        text = md_file.read_text(encoding="utf-8")
                        rel = str(md_file.relative_to(specs_root)).replace(".md", "")
                        sid = rel.replace("/", "--").replace("\\", "--")
                        status, domain, fm = _parse_spec_frontmatter(md_file, sid, text)
                        conn.execute(
                            """INSERT INTO specs(spec_id,status,domain,frontmatter_json,body,path,updated_at)
                               VALUES(?,?,?,?,?,?,?)
                               ON CONFLICT(spec_id) DO UPDATE SET
                                 status=excluded.status,
                                 domain=excluded.domain,
                                 frontmatter_json=excluded.frontmatter_json,
                                 body=excluded.body,
                                 path=excluded.path,
                                 updated_at=excluded.updated_at""",
                            (
                                sid,
                                status,
                                domain,
                                json.dumps(fm, ensure_ascii=False),
                                text,
                                str(md_file),
                                now_iso,
                            ),
                        )
                        counts["specs"] += 1
                    except Exception as exc:
                        print(f"[state-store rebuild] spec {md_file} error: {exc}", file=sys.stderr)
                        counts["errors"] += 1

            from che_core.paths import get_che_home

            bindings_path = get_che_home() / "bindings" / "registry.jsonl"
            if bindings_path.exists():
                with open(bindings_path, "r", encoding="utf-8") as f:
                    for ln in f:
                        ln = ln.strip()
                        if not ln:
                            continue
                        try:
                            e = json.loads(ln)
                            session_id = e.get("session_id")
                            if not session_id:
                                continue
                            flags_json = json.dumps(e.get("flags", {}), ensure_ascii=False)
                            data_keys = set(e.keys()) - {
                                "ts",
                                "event",
                                "session_id",
                                "status",
                                "worktree_root",
                                "flags",
                            }
                            data_json = json.dumps(
                                {k: e[k] for k in data_keys if k in e},
                                ensure_ascii=False,
                            )
                            conn.execute(
                                """INSERT INTO bindings(session_id,ts,status,worktree_root,flags_json,data_json,session_dir)
                                   VALUES(?,?,?,?,?,?,?)
                                   ON CONFLICT(session_id) DO UPDATE SET
                                     ts=excluded.ts,
                                     status=excluded.status,
                                     worktree_root=excluded.worktree_root,
                                     flags_json=excluded.flags_json,
                                     data_json=excluded.data_json,
                                     session_dir=excluded.session_dir""",
                                (
                                    session_id,
                                    e.get("ts", now_iso),
                                    e.get("status", "UNKNOWN"),
                                    e.get("worktree_root", ""),
                                    flags_json,
                                    data_json,
                                    e.get("che_session_dir"),
                                ),
                            )
                            counts["bindings"] += 1
                        except Exception:
                            counts["errors"] += 1

            try:
                for t in ("tasks", "decisions", "specs"):
                    conn.execute(f"INSERT INTO {t}_fts({t}_fts) VALUES('rebuild')")
            except sqlite3.OperationalError:
                pass

        counts["db_path"] = str(db_path)
        counts["ok"] = True
        return counts
    finally:
        conn.close()


def _rows_to_dicts(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [{k: r[k] for k in r.keys()} for r in rows]


def query_state_db(
    sql: str,
    binds: Optional[List[str]] = None,
    worktree_root: Optional[str] = None,
    as_json: bool = False,
    force: bool = False,
) -> Union[str, List[Dict[str, Any]], Dict[str, Any]]:
    binds = binds or []
    if not force:
        first_token = sql.lstrip().split(" ")[0].lower() if sql.strip() else ""
        if first_token not in {"select", "explain", "pragma"}:
            raise ValueError(
                "SQL restrito a SELECT / EXPLAIN / PRAGMA por padrão. Para modificar dados, passe --force explicitamente."
            )
    db_path = _get_state_db_path(worktree_root=worktree_root)
    if not db_path.exists():
        raise FileNotFoundError(f"State store ainda não existe em: {db_path}. Rode `che state rebuild-index` primeiro.")
    conn = _connect(db_path, read_only=(not force))
    try:
        cur = conn.execute(sql, binds)
        rows = cur.fetchall()
        dicts = _rows_to_dicts(rows)
        if as_json:
            return {
                "sql": sql,
                "binds": binds,
                "rowcount": len(dicts),
                "rows": dicts,
            }
        if not dicts:
            return "(0 rows)"
        headers = list(dicts[0].keys())
        widths = [len(h) for h in headers]
        for r in dicts:
            for i, h in enumerate(headers):
                v = str(r.get(h, ""))
                if len(v) > widths[i]:
                    widths[i] = len(v)
        sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
        lines = [sep]
        header_line = "|" + "|".join(f" {h.ljust(widths[i])} " for i, h in enumerate(headers)) + "|"
        lines.append(header_line)
        lines.append(sep)
        for r in dicts:
            row_line = "|" + "|".join(f" {str(r.get(h, '')).ljust(widths[i])} " for i, h in enumerate(headers)) + "|"
            lines.append(row_line)
        lines.append(sep)
        lines.append(f"({len(dicts)} rows)")
        return "\n".join(lines)
    finally:
        conn.close()


def sanitize_state(
    worktree_root: str,
    max_age_days: int = 180,
    max_decisions: int = 5000,
    dry_run: bool = False,
) -> Dict[str, Any]:
    paths = compute_paths(worktree_root, "state-sanitize")
    db_path = _get_state_db_path(paths=paths)
    result: Dict[str, Any] = {
        "db_path": str(db_path),
        "dry_run": dry_run,
        "max_age_days": max_age_days,
        "max_decisions": max_decisions,
        "deleted": {
            "decisions_old": 0,
            "decisions_over_cap": 0,
            "bindings_old": 0,
            "tasks_done_old": 0,
        },
        "error": None,
    }
    if not db_path.exists():
        rebuild_state_index(worktree_root)
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    cutoff = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    conn = _connect(db_path)
    try:
        with conn:
            cur = conn.execute(
                "SELECT COUNT(*) AS c FROM decisions WHERE ts < ?",
                (cutoff,),
            )
            result["deleted"]["decisions_old"] = int(cur.fetchone()["c"])
            cur = conn.execute(
                "SELECT COUNT(*) AS c FROM bindings WHERE ts < ? AND status != 'BOUND'",
                (cutoff,),
            )
            result["deleted"]["bindings_old"] = int(cur.fetchone()["c"])
            cur = conn.execute(
                """SELECT COUNT(*) AS c FROM tasks
                   WHERE status = 'DONE' AND updated_at < ?""",
                (cutoff,),
            )
            result["deleted"]["tasks_done_old"] = int(cur.fetchone()["c"])
            cur = conn.execute("SELECT COUNT(*) AS total FROM decisions")
            total_decisions = int(cur.fetchone()["total"])
            over_cap = max(0, total_decisions - max_decisions)
            result["deleted"]["decisions_over_cap"] = over_cap

            if not dry_run:
                conn.execute("DELETE FROM decisions WHERE ts < ?", (cutoff,))
                if over_cap > 0:
                    conn.execute(
                        "DELETE FROM decisions WHERE id IN (SELECT id FROM decisions ORDER BY ts ASC LIMIT ?)",
                        (over_cap,),
                    )
                conn.execute(
                    "DELETE FROM bindings WHERE ts < ? AND status != 'BOUND'",
                    (cutoff,),
                )
                conn.execute(
                    "DELETE FROM tasks WHERE status = 'DONE' AND updated_at < ?",
                    (cutoff,),
                )
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.execute("VACUUM")
    except Exception as exc:
        result["error"] = str(exc)
        print(f"[state-store sanitize] error: {exc}", file=sys.stderr)
    finally:
        conn.close()
    return result


def search_state(
    worktree_root: str,
    query_text: str,
    top_k: int = 15,
    scope: str = "all",
) -> Dict[str, Any]:
    if not query_text:
        return {"query": "", "top_k": top_k, "scope": scope, "results": []}
    db_path = _get_state_db_path(worktree_root=worktree_root)
    if not db_path.exists():
        rebuild_state_index(worktree_root)
    conn = _connect(db_path, read_only=True)
    try:
        fts_supported = True
        try:
            conn.execute("SELECT 1 FROM tasks_fts LIMIT 0")
        except sqlite3.OperationalError:
            fts_supported = False

        safe = re.sub(r"[^\w\s\-]", " ", query_text)
        q_terms = [t + "*" for t in safe.split() if t]
        fts_query = " ".join(q_terms) or query_text

        results: List[Dict[str, Any]] = []

        def add_results(label: str, rows: List[sqlite3.Row]):
            for r in rows[:top_k]:
                item: Dict[str, Any] = {"scope": label}
                for k in r.keys():
                    if k == "score":
                        item["score"] = float(r[k])
                    elif k == "rank":
                        continue
                    else:
                        item[k] = r[k]
                results.append(item)

        if fts_supported:
            if scope in ("all", "tasks", "envelopes"):
                cur = conn.execute(
                    """SELECT t.id, t.title, t.domain, t.status, t.envelope_path, bm25(tasks_fts) AS score
                       FROM tasks_fts
                       JOIN tasks t ON t.rowid = tasks_fts.rowid
                       WHERE tasks_fts MATCH ?
                       ORDER BY score ASC
                       LIMIT ?""",
                    (fts_query, top_k),
                )
                add_results("tasks", cur.fetchall())
            if scope in ("all", "decisions"):
                cur = conn.execute(
                    """SELECT d.id, d.ts, d.event, d.worktree_root, d.task_id, bm25(decisions_fts) AS score
                       FROM decisions_fts
                       JOIN decisions d ON d.id = decisions_fts.rowid
                       WHERE decisions_fts MATCH ?
                       ORDER BY score ASC
                       LIMIT ?""",
                    (fts_query, top_k),
                )
                add_results("decisions", cur.fetchall())
            if scope in ("all", "specs"):
                cur = conn.execute(
                    """SELECT s.spec_id, s.status, s.domain, s.path, bm25(specs_fts) AS score
                       FROM specs_fts
                       JOIN specs s ON s.rowid = specs_fts.rowid
                       WHERE specs_fts MATCH ?
                       ORDER BY score ASC
                       LIMIT ?""",
                    (fts_query, top_k),
                )
                add_results("specs", cur.fetchall())
        else:
            like = f"%{query_text}%"
            if scope in ("all", "tasks", "envelopes"):
                cur = conn.execute(
                    """SELECT id, title, domain, status, envelope_path
                       FROM tasks WHERE title LIKE ? OR envelope_body LIKE ?
                       LIMIT ?""",
                    (like, like, top_k),
                )
                add_results("tasks", cur.fetchall())
            if scope in ("all", "decisions"):
                cur = conn.execute(
                    """SELECT id, ts, event, worktree_root, task_id
                       FROM decisions WHERE payload LIKE ?
                       LIMIT ?""",
                    (like, top_k),
                )
                add_results("decisions", cur.fetchall())
            if scope in ("all", "specs"):
                cur = conn.execute(
                    """SELECT spec_id, status, domain, path
                       FROM specs WHERE body LIKE ?
                       LIMIT ?""",
                    (like, top_k),
                )
                add_results("specs", cur.fetchall())

        results_sorted = sorted(
            results,
            key=lambda x: x.get("score", 999999.0) if x.get("score") is not None else 999999.0,
        )
        return {
            "query": query_text,
            "top_k": top_k,
            "scope": scope,
            "fts": fts_supported,
            "results": results_sorted[:top_k],
        }
    finally:
        conn.close()
