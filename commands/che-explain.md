---
description: "Didactic explainer: what is this PR / ticket / branch about? Mermaid diagrams + attention points. Default = simple, --deep = technical."
arguments:
  - name: target
    description: "GitHub PR URL, ticket URL or key (FLO-123), branch name, or --worktree /abs/path."
    required: true
  - name: deep
    description: "Render at technical depth (10 sections, 3 diagrams) instead of the default didactic 5."
    required: false
  - name: base
    description: "Base branch for branch/worktree mode. Default: auto-detect, ask if ambiguous."
    required: false
  - name: worktree
    description: "Explicit worktree absolute path (branch/worktree mode)."
    required: false
---

IMMEDIATELY invoke **`che-explain`** Skill.

Preflight dispatch:

- **Mode A** — arg is a GitHub PR URL: `gh auth status` OK, URL parseable and reachable.
- **Mode B** — arg is a ticket URL or key (Linear / ClickUp / GitHub issue): retrieve via the matching MCP tool; if it returns nothing usable, ask the user for the description instead of guessing the scope.
- **Mode C** — arg is `--worktree /abs/path`, an absolute repo path, or a branch name: confirm the worktree, resolve the base branch, ask when ambiguous.

The skill resolves the input ONCE, then renders at the requested depth: default = 5 didactic sections + 1 flow diagram; `--deep` = 10 technical sections + architecture, sequence and flow diagrams.

Save via `che output_path "explain" "che-explain" "<related_id>" "session" "md"` → `$CHE_SESSION_DIR/explanations/<related_id>/` (NEVER inside the worktree). Deliver a condensed 4-section summary in the chat language, with the diagram re-emitted using translated labels.
