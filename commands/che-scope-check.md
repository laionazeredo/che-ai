---
description: "4-checks scope audit from PRD/ticket/task-graph against GitHub PR or local worktree. Checks: 1) full scope delivery (ACs mapped), 2) unit/e2e tests cover expected behavior, 3) required docs updated (AGENTS/README/runbooks), 4) new env vars declared in infra/env parsers. Returns verdict GREEN/YELLOW/RED."
arguments:
  - name: target
    description: "Scope source (pick 1 OR combination). Format: --prd=/abs/path.md OR --ticket=<Linear/Jira URL> OR --task-graph=/abs/task_graph.md OR --scope=<free text>."
    required: true
  - name: pr_url
    description: "Mode A (PR): GitHub PR URL. Mutually exclusive with --worktree (prio PR URL)."
    required: false
  - name: worktree
    description: "Mode B (local): absolute worktree path + base branch auto-detect. Base branch override: --base=origin/dev."
    required: false
  - name: base
    description: "Mode B only: base branch for diff. Default: auto (origin/main → origin/dev, ask if ambiguous)."
    required: false
---

IMMEDIATELY invoke **`che-scope-checker`** Skill.

Preflight dispatch (pick ONE mode):
- **Mode A (PR URL)** — arg is a valid GitHub URL `github.com/*/pull/*` → mode A. Pre: `gh auth status` OK; parse PR number. PR body text becomes an ADDITIONAL SCOPE source along with `--prd`/`--ticket`/`--task-graph`/--scope.
- **Mode B (Local Worktree)** — `--worktree` provided OR `target` is a valid absolute path to a git worktree WITHOUT PR URL. Pre: `cd <worktree> && git rev-parse --is-inside-work-tree` = `true`. Detect base branch (ask if ambiguous).

Scope source mandatory (at LEAST 1 of the 5 accepted — combination permitted):
1. `--prd=/path/prd.md` (headings ACs / Goals / OOS)
2. `--ticket=<Linear/Jira URL>` (via API GraphQL/REST)
3. `--task-graph=/path/task_graph.md` (todos os nodes status DONE)
4. `--scope="free text with ACs"`
5. **PR body** (Mode A only, extracted automatically)

If NO scope source provided → ASK user. Do not proceed without a defined scope.

Report: `$CHE_WORKSPACE_SHARED/scope-check_<slug>_<YYYYMMDD>.md` with 4 canonical sections + final verdict 🟢🟡🔴 in English.
