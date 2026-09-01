---
description: "Run a 7-step project X-Ray (structural scan) on a worktree. Writes durable project knowledge to .registry/projects/<slug>/: project_profile.md (auto-detected stack + conventions) + architecture.md (hybrid auto-fill) + appends registry.jsonl."
arguments:
  - name: worktree
    description: "Absolute worktree path to scan. If missing and no binding exists → ASK first."
    required: false
  - name: force
    description: "Optional --force flag: overwrite existing project_profile.md even if it already has content (default: skip auto-sections if file has human edits)."
    required: false
---

IMMEDIATELY invoke the **`harness-xray`** Skill.

Preflight:
1. If binding Level1 (`$HOME/.trae/bindings/registry.jsonl`, STATUS=BOUND) exists → use WORKTREE_ROOT from it.
2. If no binding AND no worktree → ASK user for absolute worktree path FIRST; create binding (§19 2-LEVEL) before proceeding.
3. Optional `--force` flag: if present → overwrite all auto-detected sections; if absent → skip any section that has a human-added H2 in project_profile.md.
