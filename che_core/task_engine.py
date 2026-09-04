import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from che_core.decisions import append_decision_jsonl
from che_core.paths import ensure_session_dirs, get_che_home
from che_core.task_graph import (
    VALID_DOMAINS,
    VALID_STATUSES,
    build_dag,
    check_task_ready,
    kahn_waves,
    parse_task_graph,
)

RESUME_SID_PREFIX = "task-resume"


def _resolve_task_paths(worktree_root: str, session_id: str = RESUME_SID_PREFIX) -> Dict[str, str]:
    paths = ensure_session_dirs(worktree_root, session_id)
    return paths


def list_tasks(worktree_root: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    filters = filters or {}
    graph = parse_task_graph(worktree_root)
    tasks = list(graph["tasks"].values())

    if filters.get("status"):
        tasks = [t for t in tasks if t["status"].upper() in set(s.upper() for s in filters["status"])]
    if filters.get("domain"):
        tasks = [t for t in tasks if t["domain"] in filters["domain"]]
    if filters.get("ready_only"):
        ready_ids = {
            check_task_ready(graph, tid)["task"]
            for tid in graph["tasks"]
            if check_task_ready(graph, tid)["ready"]
        }
        tasks = [t for t in tasks if t["id"] in ready_ids]

    status_rank = {"BLOCKED": 0, "TODO": 1, "IN_PROGRESS": 2, "SCOPE_OK": 3, "QA_OK": 4, "DONE": 5}
    tasks.sort(
        key=lambda t: (
            status_rank.get(t["status"], 99),
            t["domain"],
            t["id"],
        )
    )
    return tasks


def show_task(worktree_root: str, task_id: str) -> Dict[str, Any]:
    graph = parse_task_graph(worktree_root)
    task = graph["tasks"].get(task_id)
    if not task:
        return {"found": False, "task_id": task_id, "worktree_root": worktree_root}

    fwd, _rev = build_dag(graph)
    ready = check_task_ready(graph, task_id)

    handoff_info: List[Dict[str, Any]] = []
    for hof in task["envelope"].get("handoff_output", []):
        p = Path(graph["tasks_root"]) / hof.lstrip("/")
        handoff_info.append({"path": hof, "exists": p.exists() or Path(hof).exists()})

    return {
        "found": True,
        "task": task,
        "dependents": fwd.get(task_id, []),
        "ready": ready,
        "handoff": handoff_info,
        "graph": {
            "path": graph["path"],
            "tasks_root": graph["tasks_root"],
        },
    }


def set_status_task(
    worktree_root: str,
    task_id: str,
    status: str,
    *,
    session_id: Optional[str] = None,
    reason: Optional[str] = None,
    update_task_graph_md: bool = True,
) -> Dict[str, Any]:
    status = status.upper()
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")

    paths = _resolve_task_paths(worktree_root, session_id or f"{RESUME_SID_PREFIX}-set")
    shared = Path(paths["CHE_WORKSPACE_SHARED"])
    tg_path = shared / "task_graph.md"
    if not tg_path.exists():
        return {"ok": False, "reason": f"task_graph.md not found at {tg_path}"}

    lines = tg_path.read_text(encoding="utf-8").splitlines()
    header_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("| ID |") and "Title" in line and "Status" in line:
            header_idx = i
            break

    if header_idx < 0:
        return {"ok": False, "reason": "task_graph.md header not found"}

    replaced = False
    for i in range(header_idx + 2, len(lines)):
        line = lines[i]
        if not line.strip().startswith("|"):
            break
        parts = [p.strip() for p in line.lstrip("|").rstrip("|").split("|")]
        if len(parts) < 4:
            continue
        tid = parts[0]
        if tid == task_id:
            parts[3] = status
            new_line = "| " + " | ".join(parts) + " |"
            lines[i] = new_line
            replaced = True
            break

    if not replaced:
        return {"ok": False, "reason": f"task {task_id} not found in task_graph.md"}

    if update_task_graph_md:
        tg_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    append_decision_jsonl(
        worktree_root,
        "TASK_STATUS_UPDATE",
        json.dumps(
            {"task_id": task_id, "new_status": status, "reason": reason or "", "session_id": session_id or ""},
            ensure_ascii=False,
        ),
        session_id=session_id,
    )

    return {"ok": True, "task_id": task_id, "new_status": status, "path": str(tg_path)}


def resume_task(worktree_root: str, task_id: str, session_id: str) -> Dict[str, Any]:
    paths = ensure_session_dirs(worktree_root, session_id)
    info = show_task(worktree_root, task_id)
    if not info["found"]:
        return {"ok": False, "reason": f"task {task_id} not found"}

    task = info["task"]
    domain = task["domain"]
    if domain not in VALID_DOMAINS:
        domain = "engineering"

    flags_payload = json.dumps(
        {
            "flags": {
                "ACTIVE_DOMAIN": domain,
                "ACTIVE_TASK_ID": task_id,
                "ACTIVE_TASK_DOMAIN": domain,
                "ACTIVE_TASK_HANDOFF": info["handoff"],
            },
            "event": "TASK_RESUME",
            "active_task": task_id,
            "workspace_name": paths["CHE_WORKSPACE_NAME"],
            "worktree_slug": paths["CHE_WORKTREE_SLUG"],
        }
    )
    try:
        from che_core.registry import registry_append_jsonl

        registry_append_jsonl(session_id, "BOUND", worktree_root, flags_payload)
    except Exception as exc:
        return {"ok": False, "reason": f"registry_append failed: {exc}"}

    append_decision_jsonl(
        worktree_root,
        "TASK_RESUME",
        json.dumps(
            {
                "task_id": task_id,
                "domain": domain,
                "ready": info["ready"],
                "expert_skills": task["envelope"].get("expert_skills", []),
                "handoff_output": task["envelope"].get("handoff_output", []),
            },
            ensure_ascii=False,
        ),
        session_id=session_id,
    )

    che_home = get_che_home()
    domain_profile = che_home / "domains" / domain / "profile.md"
    domain_playbook = che_home / "domains" / domain / "playbook.md"
    domain_gates_dir = che_home / "domains" / domain / "gates"

    gates: List[str] = []
    if domain_gates_dir.is_dir():
        gates = sorted(str(p.name) for p in domain_gates_dir.iterdir() if p.suffix == ".md")

    return {
        "ok": True,
        "worktree_root": worktree_root,
        "session_id": session_id,
        "paths": paths,
        "task": {
            "id": task["id"],
            "title": task["title"],
            "domain": domain,
            "status": task["status"],
            "depends_on": task["depends_on"],
            "dependents": info["dependents"],
            "expert_skills": task["envelope"].get("expert_skills", []),
            "handoff_output": task["envelope"].get("handoff_output", []),
            "handoff_exists": info["handoff"],
        },
        "ready": info["ready"],
        "domain_context": {
            "profile": str(domain_profile) if domain_profile.exists() else None,
            "playbook": str(domain_playbook) if domain_playbook.exists() else None,
            "gates": gates,
            "gates_dir": str(domain_gates_dir) if domain_gates_dir.exists() else None,
        },
        "recommended_action": _recommended_action(domain, task),
        "envelope_path": task["envelope_path"],
    }


def _recommended_action(domain: str, task: Dict[str, Any]) -> Dict[str, Any]:
    title_lower = (task.get("title") or "").lower()
    _expert_skills = task.get("envelope", {}).get("expert_skills", [])

    cmd: Dict[str, Any]
    if domain == "ux":
        if any(x in title_lower for x in ["figma", "penpot", "design", "ui"]):
            cmd = {
                "slash": "/che-design",
                "alt": "/che-figma",
                "description": "Design specialized workflow. Use PenPot MCP or Figma bridge.",
                "gate_after": "pixel-check + a11y gates obrigatórios antes de handoff dev.",
            }
        else:
            cmd = {
                "slash": "/che-design",
                "alt": None,
                "description": "UX domain workflow.",
                "gate_after": "ux gates obrigatórios no ship.",
            }
    elif domain == "product":
        cmd = {
            "slash": "/che-prd",
            "alt": None,
            "description": "Gerar PRD aprovável no product domain.",
            "gate_after": "product gates se existirem.",
        }
    elif domain == "devops":
        cmd = {
            "slash": "/che-act",
            "alt": "/che-review",
            "description": "Devops: usar che-act com focus de infra/deploy. Se for deploy, rodar antes che-review vs dev.",
            "gate_after": "devops gates existentes no ship.",
        }
    elif domain == "copywriting" or domain == "social" or domain == "seo-analytics":
        cmd = {
            "slash": "/che-act",
            "alt": None,
            "description": f"Domínio {domain}. Fluxo SM → Developer (content task) → QA → Ship.",
            "gate_after": f"gates {domain} se definidos.",
        }
    else:
        if any(x in title_lower for x in ["test", "qa", "e2e"]):
            cmd = {
                "slash": "/che-manual-test",
                "alt": "/che-ui-testing",
                "description": "Task de testes. Iniciar por qa-manual ou ui-testing antes de implementação.",
                "gate_after": "qa gates + lint/typecheck/test threshold = 0 failing.",
            }
        else:
            cmd = {
                "slash": "/che-act",
                "alt": "/che-act --task " + task["id"],
                "description": "Engineering standard flow: SM scope capture → TDD Developer → QA → Compliance → Ship.",
                "gate_after": "lint 0 errors · typecheck 0 errors · test pass rate 100% · coverage ≥ threshold.",
            }

    return cmd


def graph_summary(worktree_root: str) -> Dict[str, Any]:
    graph = parse_task_graph(worktree_root)
    from che_core.task_graph import summarize_graph

    summary = summarize_graph(graph)
    summary["waves"] = kahn_waves(graph)
    return summary
