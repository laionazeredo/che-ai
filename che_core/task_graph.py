import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Tuple

from che_core.paths import compute_paths

VALID_STATUSES = {"TODO", "IN_PROGRESS", "SCOPE_OK", "QA_OK", "DONE", "BLOCKED"}
VALID_DOMAINS = {
    "engineering",
    "product",
    "ux",
    "devops",
    "copywriting",
    "social",
    "seo-analytics",
}


def _split_row(line: str) -> List[str]:
    line = line.strip()
    if not line.startswith("|"):
        return []
    parts = line[1:].rstrip("|").split("|")
    return [p.strip() for p in parts]


def _normalize_depends(raw: str) -> List[str]:
    if raw is None or raw == "" or raw == "-" or raw.lower() == "none":
        return []
    deps = re.split(r"[,\s;]+", raw.strip())
    out = []
    for d in deps:
        d = d.strip()
        if d:
            out.append(d)
    return out


def _normalize_domain(raw: str) -> str:
    if not raw:
        return "engineering"
    raw = raw.strip().lower()
    if raw in VALID_DOMAINS:
        return raw
    return "engineering"


def _normalize_expert_skills(raw: str) -> List[str]:
    if not raw:
        return []
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1]
    else:
        inner = raw
    items = [x.strip().strip("'\"`") for x in inner.split(",")]
    return [x for x in items if x]


def _normalize_handoff_output(raw: str) -> List[str]:
    if not raw:
        return []
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1]
    else:
        inner = raw
    items = [x.strip().strip("'\"`") for x in inner.split(",")]
    return [x for x in items if x]


def parse_task_graph(worktree_root: str, session_id: str = "task-graph-session") -> Dict[str, Any]:
    paths = compute_paths(worktree_root, session_id)
    shared = Path(paths["CHE_WORKSPACE_SHARED"])
    tg_path = shared / "task_graph.md"
    tasks_root = shared / "tasks"

    result: Dict[str, Any] = {
        "path": str(tg_path),
        "tasks_root": str(tasks_root),
        "metadata": {},
        "tasks": {},
        "order": [],
    }

    if not tg_path.exists():
        return result

    text = tg_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    metadata: Dict[str, Any] = {}
    table_header_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("- **Created:**") or line.startswith("- **Worktree:**") or line.startswith("- **Feature"):
            m = re.match(r"-\s+\*\*(.+?)\*\*:\s*(.+)", line)
            if m:
                metadata[m.group(1).strip().lower()] = m.group(2).strip()
        if line.startswith("| ID |") and "Title" in line and "Depends" in line and "Status" in line:
            table_header_idx = i
            break

    result["metadata"] = metadata

    if table_header_idx < 0:
        return result

    for i in range(table_header_idx + 2, len(lines)):
        line = lines[i]
        if not line.strip().startswith("|"):
            break
        row = _split_row(line)
        if len(row) < 4:
            continue
        tid = row[0].strip()
        if not re.match(r"^T\d+$", tid):
            continue
        title = row[1].strip() if len(row) > 1 else ""
        depends = _normalize_depends(row[2] if len(row) > 2 else "")
        status_raw = (row[3] if len(row) > 3 else "TODO").upper()
        status = status_raw if status_raw in VALID_STATUSES else "TODO"
        domain = _normalize_domain(row[4] if len(row) > 4 else "")
        done_criteria = row[5] if len(row) > 5 else ""

        envelope_path = tasks_root / tid / "envelope.md"
        envelope = _parse_envelope(envelope_path, task_id=tid, title=title)
        if envelope["domain"] != "engineering":
            domain = envelope["domain"]

        result["tasks"][tid] = {
            "id": tid,
            "title": title,
            "depends_on": depends,
            "status": status,
            "domain": domain,
            "done_criteria": done_criteria,
            "envelope_path": str(envelope_path),
            "envelope": envelope,
        }
        result["order"].append(tid)

    return result


def _parse_frontmatter_table(md_text: str, task_id: str = "", title: str = "") -> Dict[str, Any]:
    env: Dict[str, Any] = {
        "task_id": task_id,
        "title": title,
        "domain": "engineering",
        "depends_on": [],
        "worktree": "",
        "expert_skills": [],
        "handoff_output": [],
        "part_of_session": "",
        "sm_created_on": "",
    }

    meta_start = -1
    meta_end = -1
    lines = md_text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "## Metadata":
            meta_start = i
            continue
        if meta_start >= 0 and meta_end < 0:
            if line.startswith("## ") and i > meta_start + 1:
                meta_end = i
                break

    if meta_start < 0:
        return env

    sub = lines[meta_start:meta_end] if meta_end > 0 else lines[meta_start:]
    for line in sub:
        if not line.strip().startswith("|"):
            continue
        row = _split_row(line)
        if len(row) < 2:
            continue
        key = row[0].strip().lower()
        val = row[1].strip()
        if key == "task id":
            env["task_id"] = val
        elif key == "title":
            env["title"] = val
        elif key == "domain:":
            env["domain"] = _normalize_domain(val)
        elif key == "domain":
            env["domain"] = _normalize_domain(val)
        elif key == "depends on tasks":
            env["depends_on"] = _normalize_depends(val)
        elif key == "worktree":
            env["worktree"] = val
        elif key == "expert_skills:":
            env["expert_skills"] = _normalize_expert_skills(val)
        elif key == "handoff_output" or key.startswith("handoff_output"):
            env["handoff_output"] = _normalize_handoff_output(val)
        elif key == "part of session (task-id slug)":
            env["part_of_session"] = val
        elif key == "sm created on":
            env["sm_created_on"] = val

    return env


def _parse_envelope(path: Path, task_id: str = "", title: str = "") -> Dict[str, Any]:
    if not path.exists():
        return {
            "task_id": task_id,
            "title": title,
            "domain": "engineering",
            "depends_on": [],
            "worktree": "",
            "expert_skills": [],
            "handoff_output": [],
            "part_of_session": "",
            "sm_created_on": "",
            "exists": False,
            "raw": "",
        }
    text = path.read_text(encoding="utf-8")
    out = _parse_frontmatter_table(text, task_id=task_id, title=title)
    out["exists"] = True
    out["raw"] = text
    return out


def build_dag(graph: Dict[str, Any]) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    forward: Dict[str, List[str]] = defaultdict(list)
    reverse: Dict[str, List[str]] = defaultdict(list)
    for tid, task in graph["tasks"].items():
        forward.setdefault(tid, [])
        for dep in task["depends_on"]:
            if dep in graph["tasks"]:
                forward[dep].append(tid)
                reverse[tid].append(dep)
    return dict(forward), dict(reverse)


def topological_sort(graph: Dict[str, Any]) -> List[str]:
    reverse = build_dag(graph)[1]
    indeg = {t: len(reverse.get(t, [])) for t in graph["tasks"]}
    q: deque = deque(sorted([t for t, d in indeg.items() if d == 0]))
    order: List[str] = []
    while q:
        n = q.popleft()
        order.append(n)
        for child in build_dag(graph)[0].get(n, []):
            indeg[child] -= 1
            if indeg[child] == 0:
                q.append(child)
    if len(order) != len(graph["tasks"]):
        return sorted(graph["tasks"].keys())
    return order


def kahn_waves(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    reverse = build_dag(graph)[1]
    indeg = {t: len(reverse.get(t, [])) for t in graph["tasks"]}
    waves: List[Dict[str, Any]] = []
    remaining = dict(indeg)
    while remaining:
        wave_tids = sorted([t for t, d in remaining.items() if d == 0])
        if not wave_tids:
            wave_tids = sorted(remaining.keys())
        tasks_in_wave = [graph["tasks"][t] for t in wave_tids]
        domains = sorted({t["domain"] for t in tasks_in_wave})
        waves.append(
            {
                "wave": len(waves),
                "tids": wave_tids,
                "domains": domains,
                "parallelizable": len(wave_tids) > 1,
            }
        )
        for tid in wave_tids:
            remaining.pop(tid, None)
            for child in build_dag(graph)[0].get(tid, []):
                if child in remaining:
                    remaining[child] -= 1
    return waves


DONE_STATUSES = {"DONE", "QA_OK"}


def _handoff_exists(workspace_shared: str, handoff_rel: str) -> bool:
    p = Path(workspace_shared) / handoff_rel.lstrip("/")
    if p.exists():
        return True
    p_abs = Path(handoff_rel)
    return p_abs.exists()


def check_task_ready(graph: Dict[str, Any], task_id: str) -> Dict[str, Any]:
    if task_id not in graph["tasks"]:
        return {"ready": False, "reason": f"Task {task_id} not found", "pending": []}

    task = graph["tasks"][task_id]
    pending: List[Dict[str, Any]] = []
    for dep_id in task["depends_on"]:
        if dep_id not in graph["tasks"]:
            pending.append({"task": dep_id, "status": "MISSING", "reason": "dep task not in graph"})
            continue
        dep = graph["tasks"][dep_id]
        if dep["status"] not in DONE_STATUSES:
            pending.append(
                {
                    "task": dep_id,
                    "status": dep["status"],
                    "reason": f"dep status is {dep['status']}, not DONE/QA_OK",
                }
            )
        for hof in dep["envelope"].get("handoff_output", []):
            if not _handoff_exists(graph["tasks_root"], hof):
                pending.append(
                    {
                        "task": dep_id,
                        "status": "HANDOFF_MISSING",
                        "handoff": hof,
                        "reason": f"handoff output missing: {hof}",
                    }
                )

    return {
        "ready": len(pending) == 0,
        "task": task_id,
        "domain": task["domain"],
        "status": task["status"],
        "pending": pending,
        "dependents": build_dag(graph)[0].get(task_id, []),
    }


def summarize_graph(graph: Dict[str, Any]) -> Dict[str, Any]:
    counts = {s: 0 for s in VALID_STATUSES}
    by_domain: Dict[str, int] = defaultdict(int)
    for t in graph["tasks"].values():
        counts[t["status"]] = counts.get(t["status"], 0) + 1
        by_domain[t["domain"]] += 1
    return {
        "total": len(graph["tasks"]),
        "counts": dict(counts),
        "by_domain": dict(by_domain),
        "waves": kahn_waves(graph),
        "topological_order": topological_sort(graph),
    }
