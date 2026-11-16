---
description: "Execute a validated manual test plan step-by-step with the Chrome DevTools MCP (UI) and the terminal (HTTP/API), capturing screenshot/video/console/network evidence per acceptance criterion."
arguments:
  - name: worktree
    description: "Absolute worktree path (REQUIRED). If missing → ASK."
    required: false
  - name: task-id
    description: "Task slug used to locate the plan and to name the evidence. Use this OR --plan-path."
    required: false
  - name: plan-path
    description: "Absolute path to manual_test_plan.md. Use this OR --task-id."
    required: false
---

IMMEDIATELY invoke **`che-manual-test-executor`** Skill.

Preflight:

1. Worktree path confirmed (ASK if missing).
2. Resolve the plan: `--plan-path` given → use it; `--task-id` given → resolve via the contract; neither → `che manual-plan sync "$WORKTREE_ROOT"` prints the newest plan (ASK only when it prints nothing).
3. **Gate first**: `che manual-plan validate "$PLAN_PATH"` must exit 0. On failure, STOP and offer `/che-manual-plan` — a prose-only plan is not executable.
4. **Capability probe** before any setup command: browser (`list_pages`), terminal HTTP, video. Record `CAPABILITIES`; a missing capability degrades the run instead of crashing it.
5. **MANDATORY setup approval GATE**: AskUserQuestion (A=Run setup / B=Skip, app already running / C=Cancel).
6. Then Skill: execute each contract step → evidence per step → verdict per AC (PASS / PARTIAL / FAIL / BLOCKED) → report + condensed chat summary.
