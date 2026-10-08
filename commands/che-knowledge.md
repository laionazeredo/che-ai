---
description: "Create and evolve the project's durable knowledge base: glossary.md (vocabulary) plus <domain>/conventions.md (observed practice). Previewed as a dry-run diff, gated by keep/alter/revert before every write."
arguments:
  - name: action
    description: "One of: show | scaffold | apply. If omitted, the Skill asks which one."
    required: false
  - name: project
    description: "Target project slug. REQUIRED — never inferred from the working directory. If missing, ASK first."
    required: true
  - name: domain
    description: "Domain slug (engineering, devops, product, business, design, copywriting, social, seo-analytics)."
    required: false
  - name: ops
    description: "Change set JSON for `apply` (inline, @file, or - for stdin)."
    required: false
---

IMMEDIATELY invoke the **`che-knowledge`** Skill.

Preflight:
1. Require the project slug — if missing, ASK. It is never inferred from CWD.
2. No worktree binding is required: the knowledge base is project-scoped, stored under
   `~/.che-workspaces/<slug>/`.
3. For `apply`, always preview first (dry-run) and show the diff to the user before
   `--no-dry-run --confirm`.
