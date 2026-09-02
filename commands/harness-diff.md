---
description: "Lightweight diff context (NO verdict — for conversation prep). Modo A=PR URL, Modo B=--worktree local vs base branch."
arguments:
  - name: pr_url_or_worktree
    description: "GitHub PR URL (Modo A) OR --worktree /abs/path (Modo B)."
    required: true
  - name: base
    description: "Base branch for Modo B. Default: origin/main or origin/dev (auto-detect, ask if ambiguous)."
    required: false
  - name: worktree
    description: "Alias: explicit --worktree for Modo B."
    required: false
---

IMMEDIATELY invoke **`harness-diff-context`** Skill.

Preflight dispatch:
- **Modo A**: if arg looks like a GitHub PR URL → `gh auth status` OK, URL parseable/reachable.
- **Modo B**: if `--worktree /abs/path` given (or arg is absolute path) → confirm worktree, detect base branch (ask if ambiguous).

Skill delivers 5-section context report (high-level / module changes / CI-checks or buckets / light risks / 3 talking points) → saved via `harness_output_path "diff_context" "context-report" "<pr-N or local>" "session" "md"` → inside `$HARNESS_SESSION_DIR/diff_contexts/<related_id>/` (NEVER inside `<WORKTREE_ROOT>/.trae`).
