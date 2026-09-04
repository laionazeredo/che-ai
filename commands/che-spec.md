---
description: "Generate or update a Che Execution Specification (SPEC). Standalone, or called by /che-act. Accepts 4 inputs: existing spec, ticket URL, legacy-project PRD .md path, inline description."
arguments:
  - name: input
    description: "One of: path-to-existing-spec, ticket-URL, path-to-legacy-project-PRD.md, or inline description text. Optional; if omitted, interactive prompt picks source."
    required: false
  - name: worktree
    description: "Absolute worktree path. If missing and no binding exists, ASK first before proceeding."
    required: false
  - name: slug
    description: "Short slug for spec filename (used in spec_<slug>.md). Ex: api-authn-fail-closed. Optional, derived if missing."
    required: false
---

IMMEDIATELY invoke the **`che-spec`** Skill.

Preflight:
1. If binding Level1 (`$HOME/.trae/bindings/registry.jsonl`, STATUS=BOUND) exists for current session → use WORKTREE_ROOT from it.
2. If no binding AND no worktree argument provided → ASK user for absolute worktree path FIRST; create binding (§19 2-LEVEL) before proceeding.
3. Collect optional `input` type and `slug`; if omitted, Skill resolves interactively during §0 Source Selection.
