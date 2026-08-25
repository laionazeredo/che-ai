---
description: "Read and summarize all entries from current session's decision.log.md (in Portuguese)."
arguments:
  - name: worktree
    description: "Worktree absolute path. If missing → ASK."
    required: false
---

Lightweight inline command (no Skill needed):

1. If worktree missing → ASK.
2. Locate active session folder `.trae/<task-id>/` (ask user if ambiguous / multiple present).
3. Read `decision.log.md`.
4. If empty/missing → "Nenhuma decisão registrada nesta sessão ainda."
5. Otherwise → summarize entries IN PORTUGUESE, grouped by decision type (SKIP GATE / SCOPE CHANGE / RISK ACCEPTED / etc.), with date + reason each.
