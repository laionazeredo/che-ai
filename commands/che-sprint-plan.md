---
description: "Build an evidence-based sprint plan from a board or ticket links. Triages ready / needs-clarification / blocked, maps dependencies, asks everything unclear, then produces a day-by-day plan with parallel waves (≤ parallelism, default 3). Saves sprint-plan.md under ~/.che-workspaces/<slug>/sprints/<start>_<end>__<name>/. Supports --add/--remove."
arguments:
  - name: source
    description: "Board name or comma-separated ticket links (Linear/GitHub/Airtable). Optional; if omitted, ask."
    required: false
  - name: start
    description: "Sprint start date YYYY-MM-DD. Optional."
    required: false
  - name: end
    description: "Sprint end date YYYY-MM-DD. Optional."
    required: false
  - name: name
    description: "Short sprint name/slug. Optional."
    required: false
  - name: project
    description: "Target project slug. REQUIRED if not already bound."
    required: false
  - name: parallelism
    description: "Max concurrent tasks per wave. Default 3; ask to confirm."
    required: false
  - name: action
    description: "Optional update: --add <links> or --remove <links> on an existing sprint plan."
    required: false
---

IMMEDIATELY invoke the **`che-sprint-plan`** Skill.

Preflight:
1. If no project slug is known and no worktree binding exists → ASK the project slug FIRST.
2. Collect source/start/end/name/parallelism/action from args; if missing, the Skill asks.
3. For `--add`/`--remove`: resolve the target sprint (bound sprint, else ask — default the most recent open sprint).
