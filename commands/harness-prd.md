---
description: "Evidence-based PRD generator — deep repo analysis first, then 4-batch questionnaire mapped to strict 15-section template."
arguments:
  - name: link
    description: "Linear/Jira ticket URL (use this OR --scope)."
    required: false
  - name: scope
    description: "Free-text scope description (use this OR --link)."
    required: false
  - name: worktree
    description: "Absolute path of confirmed worktree. If missing, ASK first."
    required: false
  - name: output
    description: "Output PRD path. Default: .trae/<task-id>/prd-<slug>.md (or docs/prd/<area>/<slug>.md if folder exists)."
    required: false
---

IMMEDIATELY invoke the **`harness-prd-generator`** Skill.

Preflight rules (DO BEFORE Skill):
1. If worktree not confirmed → ASK user for absolute worktree path FIRST.
2. Confirm input source: (a) Linear/Jira link given → use; (b) --scope text given → use; (c) none → AskUserQuestion which input mode.
3. Ask output location: default `.trae/<task-id>/prd-<slug>.md` vs `docs/prd/<area>/<slug>.md` vs custom.

Then Skill runs: (1) CRITICAL 4-dimension repo analysis, (2) 4-batch iterative questionnaire, (3) GAP auto-check P0 flags, (4) write PRD, (5) executive review menu.
