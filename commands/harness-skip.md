---
description: "Override a quality/compliance gate. Logs skip with reason. EXTREME CAUTION — especially compliance-heavy."
arguments:
  - name: gate
    description: "Gate name: scope / qa / compliance-light / compliance-heavy (REQUIRED, exact)."
    required: true
  - name: task_or_all
    description: "Task-ID slug, or literal ALL (REQUIRED)."
    required: true
  - name: reason
    description: "Reason for skip (REQUIRED — will be logged verbatim in decision.log)."
    required: true
  - name: worktree
    description: "Worktree absolute path. If missing → ASK."
    required: false
---

Lightweight inline command (no Skill needed):

1. If worktree missing → ASK.
2. If reason missing → ASK user before proceeding.
3. For `compliance-heavy` gate:
   - Require EXPLICIT confirmation TWICE from user.
   - Print HUGE warning (PT-BR): "Isso vai liberar sem checagem de segurança profunda. Continuar mesmo assim?"
4. Append to `decision.log.md` inside `.trae/<task-id>/`:
   `[<date>] [SKIP GATE] <gate> — reason: <reason> — user-approved`
5. Mark gate in TASK GRAPH as passed with skip annotation:
   e.g. `QA_OK (SKIPPED — see decision.log)`
