---
description: "Generate or update a Che Execution Specification (SPEC). Standalone, or called by /che-act. Accepts 4 inputs: existing spec, ticket URL, legacy-project PRD .md path, inline description."
arguments:
  - name: input
    description: "One of: path-to-existing-spec, ticket-URL, path-to-legacy-project-PRD.md, or inline description text. Optional; if omitted, interactive prompt picks source."
    required: false
  - name: worktree
    description: "Absolute worktree path. REQUIRED. If missing and no binding exists, ASK first."
    required: true
  - name: project
    description: "Target project slug (L2). REQUIRED. If missing, ASK user for a valid project from the current workspace."
    required: true
  - name: slug
    description: "Short slug for spec filename (used in spec_<slug>.md). Ex: api-authn-fail-closed. Optional, derived if missing."
    required: false
---

IMMEDIATELY invoke the **`che-spec`** Skill.

Preflight:
1. If binding Level1 exists for current session → use WORKTREE_ROOT from it.
2. If no binding OR no project argument provided → ASK user for absolute worktree path AND target project slug FIRST.
3. Verify if the project belongs to the resolved workspace.
4. create binding (§19 2-LEVEL) before proceeding.
3. Collect optional `input` type and `slug`; if omitted, Skill resolves interactively during §0 Source Selection.
