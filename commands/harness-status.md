---
description: "Print concise CURRENT harness session status from task_graph.md. No skill invocation needed."
arguments:
  - name: worktree
    description: "Worktree absolute path. If missing → ASK first."
    required: false
---

Lightweight inline command (no Skill needed):

1. If worktree not confirmed → ASK user for absolute worktree path FIRST.
2. Look for `task_graph.md` inside `<WORKTREE_ROOT>/.trae/<task-id>/`.
3. If not found → reply (in Portuguese):
   "Nenhuma sessão do harness ativa nesta worktree. Use `/harness-start`."
4. If found → print (in Portuguese):
   - Task currently IN_PROGRESS + current phase (scope/qa/compliance)
   - Counts: Total / TODO / SCOPE_OK / QA_OK / DONE / BLOCKED
   - Blocked tasks list, if any
   - Warnings: tasks close to exceeding 2 iterations
   - Full folder path `.trae/<task-id>/`
