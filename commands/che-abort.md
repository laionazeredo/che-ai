---
description: "Mark che session as ABORTED. Writes status to session.md + task_graph.md. Does NOT delete files."
arguments:
  - name: worktree
    description: "Worktree absolute path. If missing → ASK."
    required: false
---

Lightweight inline command (no Skill needed):

1. If worktree missing → ASK.
2. Ask user CONFIRMATION: "Tem certeza que quer abortar esta sessão do che? As alterações de código na worktree serão mantidas, mas a sessão será marcada como ABORTED. (Sim / Cancelar)".
3. If confirmed:
   **IMPORTANTE: RESOLVER PATHS VIA CONTRATO SESSIONS — NUNCA dentro da worktree:**
   `source "$HOME/.trae/contracts/che_sessions_contract.sh" && che_compute_paths "$WORKTREE_ROOT" "$SESSION_ID" && che_ensure_session_dirs "$WORKTREE_ROOT"`
   a. Write `STATUS: ABORTED` (with timestamp + reason if given) into `$CHE_SESSION_DIR/session.md`.
   b. Write `STATUS: ABORTED` into `$CHE_WORKSPACE_SHARED/task_graph.md` (task_graph lives in workspace-shared per worktree, not per-session).
   c. Append 1 entry: `che_append_decision_jsonl "$WORKTREE_ROOT" "SESSION_ABORTED" '{"reason":"user confirmed","status":"ABORTED"}'`
   d. Reply to user (PT-BR): "Sessão abortada. Arquivos de código na worktree foram mantidos. Dados da sessão preservados em `$CHE_SESSION_DIR` e `$CHE_WORKSPACE_SHARED` (FORA da sua worktree — não vão aparecer em PRs)."
4. If user cancels → no-op.
