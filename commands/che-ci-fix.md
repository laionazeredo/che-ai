---
description: "Diagnose and fix failing GitHub Actions CI. Classify root cause → minimal fix plan → apply + push."
arguments:
  - name: actions_run_url_or_pr_url
    description: "GitHub Actions RUN URL OR PR URL (REQUIRED)."
    required: true
  - name: worktree
    description: "Absolute worktree path. If missing, ASK."
    required: false
---

IMMEDIATELY invoke **`che-ci-fixer`** Skill.

Preflight:
1. `gh auth status` OK.
2. Worktree confirmed (ASK if missing).
3. Skill: pull failed jobs/steps via `gh run view` / `gh pr checks` → classify R1-R9 (build/lint/typecheck/test/flaky/deps-lockfile/CI-YAML/migration/INFRA-EXTERNAL) → per-job minimal fix plan → user APPROVES → implement → verify locally → conventional-commit ship.
