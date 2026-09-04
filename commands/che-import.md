---
description: "Import project durable data from a .tar.gz archive."
arguments:
  - name: path
    description: "Path to the .tar.gz archive to import."
    required: true
  - name: workspace
    description: "Target workspace name. Optional."
    required: false
---

Imports a previously exported Che project archive. Handles naming conflicts by appending a unique suffix if the project or worktree already exists on this machine.

**Agent action:**
1. Execute: `python3 -m che_core.cli import "$PATH" ${WORKSPACE:+--workspace "$WORKSPACE"}`.
2. Parse JSON response and report the new slugs and directories to the user.
