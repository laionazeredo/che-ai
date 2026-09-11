---
description: "Print concise CURRENT che session status from task_graph.md. No skill invocation needed."
arguments:
  - name: worktree
    description: "Worktree absolute path. If missing → ASK first."
    required: false
---

Lightweight inline command (no Skill needed):

1. If worktree not confirmed → ASK user for absolute worktree path FIRST.
2. Run `eval "$(che compute_paths WORKTREE_ROOT SESSION_ID)"`; look for `task_graph.md` at `$CHE_WORKSPACE_SHARED/task_graph.md` (strictly outside worktree; never inside `<WORKTREE_ROOT>/.trae/`).
3. If not found → reply (in English):
   "No active Che session in this worktree. Use `/che-act`."
4. If found → print (in English):
   - Task currently IN_PROGRESS + current phase (scope/qa/compliance)
   - Counts: Total / TODO / SCOPE_OK / QA_OK / DONE / BLOCKED
   - Blocked tasks list, if any
   - Warnings: tasks close to exceeding 2 iterations
   - Artifact paths (outside worktree): `$CHE_WORKSPACE_SHARED/` durable + `$CHE_SESSION_DIR/` ephemeral
