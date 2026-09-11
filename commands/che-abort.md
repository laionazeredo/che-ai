---
description: "Mark che session as ABORTED. Writes status to session.md + task_graph.md. Does NOT delete files."
arguments:
  - name: worktree
    description: "Worktree absolute path. If missing → ASK."
    required: false
---

Lightweight inline command (no Skill needed):

1. If worktree missing → ASK.
2. Ask user CONFIRMATION: "Are you sure you want to abort this Che session? Code changes in the worktree will be kept, but the session will be marked as ABORTED. (Yes / Cancel)".
3. If confirmed:
   **IMPORTANT: RESOLVE PATHS VIA `che` CLI — NEVER inside the worktree:**
   `eval "$(che compute_paths "$WORKTREE_ROOT" "$SESSION_ID")" && che ensure_dirs "$WORKTREE_ROOT" "$SESSION_ID"`
   a. Write `STATUS: ABORTED` (with timestamp + reason if given) into `$CHE_SESSION_DIR/session.md`.
   b. Write `STATUS: ABORTED` into `$CHE_WORKSPACE_SHARED/task_graph.md` (task_graph lives in workspace-shared per worktree, not per-session).
   c. Append 1 entry: `che decision_append "$WORKTREE_ROOT" "SESSION_ABORTED" '{"reason":"user confirmed","status":"ABORTED"}'`
   d. Reply to user (English): "Session aborted. Code files in the worktree were kept. Session data preserved in `$CHE_SESSION_DIR` and `$CHE_WORKSPACE_SHARED` (OUTSIDE your worktree — they will not appear in PRs)."
4. If user cancels → no-op.
