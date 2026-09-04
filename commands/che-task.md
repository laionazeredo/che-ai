---
description: "Cross-domain task picker, resumer and status manager for the Kahn Wave task graph. 5 subcommands: list | show TID | resume TID | set-status TID STATUS | graph-summary. Binds ACTIVE_DOMAIN + ACTIVE_TASK_ID automatically and recommends the correct domain-specialized slash command."
arguments:
  - name: worktree
    description: "Absolute worktree path. If missing and session has a BOUND binding → use binding WORKTREE_ROOT."
    required: false
  - name: subcommand
    description: "Required positional: list | show <TID> | resume <TID> | set-status <TID> <TODO|IN_PROGRESS|SCOPE_OK|QA_OK|DONE> | graph-summary. Examples: /che-task list / /che-task show T3 / /che-task resume T3 /che-task set-status T3 IN_PROGRESS"
    required: true
---

Invokes the **task engine** (`che_core.task_engine`) on top of the L3 shared `task_graph.md` and per-task `envelope.md` artifacts. This is the **entry point for multi-session and cross-domain work**: any agent or developer window can call `che-task resume TID` to take ownership of a task from the shared graph; the engine auto-loads the correct domain profile/playbook and suggests the right downstream slash command (UX → `/che-design`, Product → `/che-prd`, Engineering/DevOps/Copy/Social/SEO → `/che-act`).

**Preflight:**
1. If session already has a BOUND Level 1 registry entry with WORKTREE_ROOT → use that as default. If user passed an explicit `worktree` and it differs → warn and ask confirm switch (che-act §0.1 rule 4).
2. If no binding AND no `worktree` → call AskUserQuestion with ≤2 concrete paths + "other (type)".
3. After worktree resolved → run: `python3 -m che_core.cli ensure-dirs "$WORKTREE_ROOT"` once to guarantee L2/L3/L4 folders exist.

**Subcommand dispatch:**

| Subcommand | CLI invocation | Expected agent action after |
|---|---|---|
| `list [--status STATUS] [--domain SLUG] [--ready-only]` | `python3 -m che_core.cli task list "$WORKTREE_ROOT" [flags] --json` | Print a formatted table to user: `ID │ Status │ Domain │ Title │ Ready? │ Dependents`. Group ready-to-run tasks by Kahn wave (parallelism hint). If `--ready-only`: show only tasks whose deps are ALL DONE/QA_OK AND handoff_output files exist. |
| `show <TID>` | `python3 -m che_core.cli task show "$WORKTREE_ROOT" "<TID>" --json` | Show: (1) task metadata + status, (2) envelope fields (domain, expert_skills, handoff_output), (3) dependency tree (parents/dependents), (4) ready check result with per-dep failure reason if not ready, (5) recommended downstream slash command. |
| `resume <TID>` | `python3 -m che_core.cli task resume "$WORKTREE_ROOT" "<TID>" "$(che_current_session_id)" --json` | **This is the key multi-session hook.** Engine: (a) reads envelope domain/expert_skills, (b) writes a NEW BOUND entry into Level 1 registry with `flags:{ACTIVE_DOMAIN, ACTIVE_TASK_ID, ACTIVE_TASK_DOMAIN, ACTIVE_TASK_HANDOFF}`, (c) appends `TASK_RESUME` to decisions.log.jsonl, (d) auto-loads domain profile.md + playbook.md (same as che-act §0.3 steps 4b–4d), (e) returns `{recommended_slash_command, description, expert_skills[]}`. Agent MUST: display the recommendation prominently and ask user Y/n before running the recommended command (default Y = run it). If user chooses N → ask which command they want instead. |
| `set-status <TID> <STATUS>` | `python3 -m che_core.cli task set-status "$WORKTREE_ROOT" "<TID>" "<STATUS>" --json` | Update `task_graph.md` Status column IN-PLACE for the row. Append a single decision.log line: `TASK_STATUS TID=.. OLD=.. NEW=.. by=session_id`. Re-run show TID after so user can confirm change. |
| `graph-summary` | `python3 -m che_core.cli task graph-summary "$WORKTREE_ROOT" --json` | Print summary counts: Total tasks / by status / by domain / Kahn waves count / ready count / blocked count. |
