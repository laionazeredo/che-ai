---
description: "Lightweight diff context (NO verdict — for conversation prep). Mode A=PR URL, Mode B=--worktree local vs base branch."
arguments:
  - name: pr_url_or_worktree
    description: "GitHub PR URL (Mode A) OR --worktree /abs/path (Mode B)."
    required: true
  - name: base
    description: "Base branch for Mode B. Default: origin/main or origin/dev (auto-detect, ask if ambiguous)."
    required: false
  - name: worktree
    description: "Alias: explicit --worktree for Mode B."
    required: false
---

IMMEDIATELY invoke **`che-diff-context`** Skill.

Preflight dispatch:
- **Mode A**: if arg looks like a GitHub PR URL → `gh auth status` OK, URL parseable/reachable.
- **Mode B**: if `--worktree /abs/path` given (or arg is absolute path) → confirm worktree, detect base branch (ask if ambiguous).

Skill delivers 5-section context report (high-level / module changes / CI-checks or buckets / light risks / 3 talking points) → saved via `che output_path "diff_context" "context-report" "<pr-N or local>" "session" "md"` → inside `$CHE_SESSION_DIR/diff_contexts/<related_id>/` (NEVER inside `<WORKTREE_ROOT>/.trae`).
