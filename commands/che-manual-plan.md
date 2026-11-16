---
description: "Creates or updates the manual test plan as an EXECUTABLE contract: `che manual-plan sync` scaffolds or migrates it (idempotent), the skill fills each acceptance criterion's yaml block from the SPEC / ticket / diff, and `che manual-plan validate` is the gate. Use before /che-manual-test (which executes it) or /che-manual-verification (which renders it for a layperson)."
arguments:
  - name: worktree
    description: "Absolute worktree path (REQUIRED). If missing → ASK."
    required: false
  - name: path
    description: "Explicit plan file to update. Default: the newest known plan, else a new one is created."
    required: false
  - name: slug
    description: "Folder slug used when a new plan is created (e.g. feat-refunds). Default: manual-plan."
    required: false
---

IMMEDIATELY invoke **`che-manual-plan`** Skill.

Preflight dispatch:

1. **Worktree** confirmed (ask when missing). Never infer it from the current directory.
2. **Source of truth, first match wins** — existing plan · Approved SPEC in `$CHE_WORKSPACE_SHARED/specs/` · ticket · diff. Never invent an acceptance criterion.
3. **Scaffold or migrate**: `che manual-plan sync "$WORKTREE_ROOT" --slug "<slug>"` → take the printed path as `PLAN_PATH`. A legacy prose plan is migrated in place by the same command.
4. **Fill every contract** — driver, lane, base_url, evidence, severity and the steps. Locators are accessibility-first (`role`+`name`, `label`, `text`); CSS/XPath are rejected. Assertions must be literal text.
5. **Gate**: `che manual-plan validate "$PLAN_PATH"` must exit 0. Fix the failing `MP-` lines (max two rounds); never weaken a check to silence it.
6. **Report** in four sections: status · coverage per driver · what a human must still do · next command.
