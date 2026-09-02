---
description: "Execute manual_test_plan.md step-by-step via Playwright MCP (real browser interactions + screenshot evidence)."
arguments:
  - name: worktree
    description: "Absolute worktree path (REQUIRED). If missing → ASK."
    required: false
  - name: task-id
    description: "Task slug inside worktree/.trae/. Looks for manual_test_plan.md there. Use this OR --plan-path."
    required: false
  - name: plan-path
    description: "Absolute path to manual_test_plan.md file. Use this OR --task-id."
    required: false
---

IMMEDIATELY invoke **`harness-manual-test-executor`** Skill.

Preflight:
1. Worktree path confirmed (ASK if missing).
2. Resolve manual_test_plan.md: (a) --plan-path given → use; (b) --task-id given → resolve via contract: `<HARNESS_WORKSPACE_SHARED>/tasks/<task-id>/manual_test_plan.md` (NEVER inside worktree/.trae/); (c) neither → AskUserQuestion.
3. Parse plan (§0 Setup, AC steps, Smoke S1..S5, HUMAN_ONLY items).
4. **GATE setup approval OBRIGATÓRIO (before any shell setup command)**: AskUserQuestion (A=Run setup / B=Skip app already running / C=Cancel).
5. Then Skill: execute ACs via Playwright/HTTP driver → evidence per step → build 8-section final report → condensed chat summary.
