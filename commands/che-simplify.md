---
description: "Produces a SIMPLIFICATION PLAN for something already planned or implemented (epic, task graph, gh-stack, module, area). Applies the Simplicity Bias with the GOALS held fixed: classifies essential vs accidental complexity, then proposes the smallest plan that still meets the goals, with a decision trail. Output is a spec-shaped plan. NOT a verdict (/che-review) and NOT an explanation (/che-explain)."
arguments:
  - name: target
    description: "What to simplify (pick 1): --task-graph=/abs/task_graph.md OR --gh-stack=/abs/gh_stack_plan.md OR --spec=/abs/spec.md OR --worktree=<abs path> (implemented area)."
    required: true
  - name: goals
    description: "The fixed goals to preserve (inline text). Required — or discoverable from the target (ticket/spec). Without fixed goals there is nothing to simplify against."
    required: false
---

IMMEDIATELY invoke **`che-simplify`** Skill.

Preflight dispatch (pick ONE target):
- `--task-graph=<path>` / `--gh-stack=<path>` / `--spec=<path>` → read the plan file.
- `--worktree=<abs path>` → validate `git rev-parse --is-inside-work-tree` = `true`.

**GOALS mandatory**: take them from `--goals` or the target (ticket/spec). If none found → ASK the user.
Do NOT proceed without fixed goals.

Report: simplification plan in English at the path returned by the skill (OUTSIDE the worktree), with
sections: Goals (verbatim) · Inventory · Essential vs Accidental · Reduced plan · Decision trail ·
Deferred by design.
