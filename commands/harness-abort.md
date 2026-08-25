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
   a. Write `STATUS: ABORTED` (with timestamp + reason if given) into `.trae/<task-id>/session.md`.
   b. Write `STATUS: ABORTED` into `.trae/<task-id>/task_graph.md`.
   c. Reply to user (PT-BR): "Sessão abortada. Arquivos de código na worktree foram mantidos. Pasta `.trae/<task-id>/` preservada para referência."
4. If user cancels → no-op.
