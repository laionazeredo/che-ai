---
description: "Generate an immediate interim session summary (even if not all tasks are done)."
arguments:
  - name: worktree
    description: "Worktree absolute path. If missing → ASK."
    required: false
---

Lightweight inline command (no Skill needed):

1. If worktree missing → ASK.
2. Locate active `.trae/<task-id>/` folder.
3. Assemble interim summary using the final_summary structure:
   - Task context + worktree
   - What's DONE so far (with file references)
   - What's IN_PROGRESS / TODO
   - Any BLOCKED items + blockers
   - Risks / open questions
4. Deliver in condensed format (§18 engineering-contracts: 250-500 words, 4 sections).
