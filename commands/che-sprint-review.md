---
description: "Review a finished sprint. Gathers ticket terminal statuses and dates per provider (GitHub via gh api, Linear/Airtable via MCP; else ask), verifies delivery against sprint-plan.md, and writes sprint-review.md with a per-task report + project metrics."
arguments:
  - name: sprint
    description: "Sprint folder id or path. Optional; if omitted, list sprints and ask."
    required: false
  - name: project
    description: "Target project slug. REQUIRED if not already bound."
    required: false
---

IMMEDIATELY invoke the **`che-sprint-review`** Skill.

Preflight:
1. If no project slug is known → ASK first.
2. Resolve the target sprint (bound sprint, else list `~/.che-workspaces/<slug>/sprints/` and ask — default the most recently ended sprint).
3. Read sprint-plan.md as the source of truth; then gather per-task status/dates from the ticket provider.
