---
description: "End-of-task ship: atomic conventional commits → push → DRAFT PR → assign user."
arguments:
  - name: ticket
    description: "Linear/Jira ticket reference. Ex: FLO-123. Optional."
    required: false
  - name: slug
    description: "Branch/task slug. Ex: feat-stripe-connect. Optional."
    required: false
  - name: draft-pr-title
    description: "Override automatic PR title. Optional."
    required: false
  - name: worktree
    description: "Absolute worktree path. If missing, ASK first."
    required: false
---

IMMEDIATELY invoke **`che-ship`** Skill.

Preflight:
1. If worktree missing → ASK.
2. `gh auth status` must be OK.
3. No secret files staged (check git diff --cached for .env, keys, etc.).
4. Then Skill: propose atomic commit plan → user APPROVES → apply commits → push → build **readable PR body** (default English, 5 canonical sections, acronyms expanded first use, every change explains user impact, risks explain consequences) from manual_test_plan.md + `PR_DESCRIPTION_TEMPLATE.md` filled style reference → open DRAFT PR → assign @me.
