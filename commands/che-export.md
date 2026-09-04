---
description: "Export project durable data (architecture, business logic, etc.) to a portable archive."
arguments:
  - name: worktree
    description: "Absolute worktree path of the project to export."
    required: true
  - name: output
    description: "Target path for the exported .tar.gz archive."
    required: false
---

Exports the perennial knowledge of the current project (L2 Project Metadata + L3 Worktree Shared Strategy) to a portable archive. Excludes ephemeral session data.

**Agent action:**
1. Resolve `WORKTREE_ROOT`.
2. Determine `output` path (default: `$HOME/che-export-<project-slug>.tar.gz`).
3. Execute: `python3 -m che_core.cli export "$WORKTREE_ROOT" "$OUTPUT_PATH"`.
4. Report success and file location to the user.
