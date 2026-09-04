---
description: "Interactive: capture or read the durable Product Context + Roadmap for a project. Product Context = 8 mandatory sections (pitch, 3 personas, domain keywords, integrations, 5-10 hard invariants, compliance risks, auth roles matrix, ref URLs). Roadmap = 4 blocks (confirmed/planned/backlog/FORA-ESCOPO). Stored in .registry/projects/<slug>/ alongside xray output."
arguments:
  - name: worktree
    description: "Absolute worktree path to find the project registry slot. If missing and no binding exists → ASK first."
    required: false
  - name: mode
    description: "One of: default (interactive fill-in) | --show (read-only summary) | --bootstrap (write empty templates fast). Default: interactive."
    required: false
---

IMMEDIATELY invoke the **`che-onboarding`** Skill.

Preflight:
1. If binding Level1 exists → use WORKTREE_ROOT from it; project slug is derived from git origin (never from branch name).
2. If no binding AND no worktree → ASK first; create binding (§19 2-LEVEL).
3. Mode routing:
   - `--show` → read product_context.md + architecture.md + roadmap.md and print a structured PT-BR summary (never propose edits here).
   - `--bootstrap` → write empty templates with placeholder H2s fast (no interactive questions), then print paths.
   - default (no flag) → walk 8 product_context questions interactively then 4 roadmap blocks; write to registry files after each explicit user confirmation.
