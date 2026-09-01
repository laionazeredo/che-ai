---
description: "Mark harness session as ABORTED. Writes status to session.md + task_graph.md. Does NOT delete files."
arguments:
  - name: worktree
    description: "Worktree absolute path. If missing → ASK."
    required: false
---

Lightweight inline command (no Skill needed):

1. If worktree missing → ASK.
2. Ask user CONFIRMATION: "Tem certeza que quer abortar esta sessão do harness? As alterações de código na worktree serão mantidas, mas a sessão será marcada como ABORTED. (Sim / Cancelar)".
3. If confirmed:
   **IMPORTANTE: RESOLVER PATHS VIA CONTRATO SESSIONS — NUNCA dentro da worktree:**
   `source "$HOME/.trae/contracts/harness_sessions_contract.sh" && harness_compute_paths "$WORKTREE_ROOT" "$SESSION_ID" && harness_ensure_session_dirs "$WORKTREE_ROOT"`
   a. Write `STATUS: ABORTED` (with timestamp + reason if given) into `$HARNESS_SESSION_DIR/session.md`.
   b. Write `STATUS: ABORTED` into `$HARNESS_WORKSPACE_SHARED/task_graph.md` (task_graph lives in workspace-shared per worktree, not per-session).
   c. Append 1 entry: `harness_append_decision_jsonl "$WORKTREE_ROOT" "SESSION_ABORTED" '{"reason":"user confirmed","status":"ABORTED"}'`
   d. Reply to user (PT-BR): "Sessão abortada. Arquivos de código na worktree foram mantidos. Dados da sessão preservados em `$HARNESS_SESSION_DIR` e `$HARNESS_WORKSPACE_SHARED` (FORA da sua worktree — não vão aparecer em PRs)."
4. If user cancels → no-op.
