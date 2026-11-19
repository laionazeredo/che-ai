---
description: "YOLO end-to-end: Approved SPEC → implement every slice → ship DRAFT PR → run the manual test plan → attach evidence → mark the PR ready for review. Stops and hands back on any gate block."
arguments:
  - name: spec
    description: "Path to the Approved SPEC .md. Optional: discovered when omitted."
    required: false
  - name: worktree
    description: "Absolute worktree path. REQUIRED. If missing, ASK first."
    required: true
  - name: project
    description: "Target project slug (L2). REQUIRED. If missing, ASK."
    required: true
  - name: slug
    description: "Task slug identifier. Ex: feat-stripe-connect."
    required: false
  - name: qa
    description: "QA gate profile: minimal | normal | full. Default: minimal."
    required: false
  - name: max-slices
    description: "Abort if the task graph has more than N slices. Default: 8."
    required: false
---

IMMEDIATELY invoke the **`che-yolo`** Skill.

Preflight:
1. If worktree or project missing → ASK first. Never infer either from the current directory.
2. **Approved SPEC is mandatory.** Missing, Draft or failing `che spec validate` → STOP and offer `/che-spec`. YOLO never approves a spec on the user's behalf.
3. `gh auth status` must be OK.
4. State in one short block what will run unattended and which gates still block (scope, review, compliance, QA, domain). Then start.
5. Skill runs: `che-act` (REVIEW_MODE=FINAL) → manual test plan gate → `che-ship` → `che-manual-test-executor` → PR evidence comment + `gh pr ready` → final report.
