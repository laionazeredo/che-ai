---
description: "Full che feature/bug loop: scope capture → TASK GRAPH → dev/qa/compliance → ship. Auto-detects serial vs parallel."
arguments:
  - name: scope
    description: "Scope text or PRD path inline. Optional."
    required: false
  - name: worktree
    description: "Absolute worktree path. REQUIRED. If missing, ASK first."
    required: true
  - name: project
    description: "Target project slug (L2). REQUIRED. If missing, ASK user for a valid project."
    required: true
  - name: slug
    description: "Task slug (folder name inside .trae/). Ex: feat-stripe-connect."
    required: false
  - name: spec
    description: "Path to approved PRD/spec .md. Optional."
    required: false
---

IMMEDIATELY invoke the **`che-act`** Skill.

Preflight:
1. If worktree not confirmed OR project missing → ASK user for absolute worktree path AND target project slug FIRST.
2. Collect scope/slug/spec from args; if missing, Skill captures during Scope Capture phase.
3. Skill auto-detects serial vs parallel; falls back serial if any precondition fails.
