---
description: "Sanitize the Che state store: purge old decisions (default > 180 days), trim decisions count to a max cap (default 5000 most recent), remove RELEASED/old bindings (> max-age), remove tasks marked DONE older than max-age. Always supports --dry-run to preview the impact before running."
arguments:
  - name: worktree
    description: "Absolute worktree path. If missing and session has a BOUND binding → uses binding WORKTREE_ROOT."
    required: false
  - name: max_age_days
    description: "Integer. Keep records newer than this (in days). Default = 180. Affects: decisions older than, non-BOUND bindings older than, tasks with status=DONE updated older than."
    required: false
  - name: max_decisions
    description: "Integer. Hard cap on total number of decisions rows to keep in the state store (most recent preserved). Default = 5000."
    required: false
  - name: dry_run
    description: "Optional flag --dry-run. If passed → only computes the would-be counts and returns JSON WITHOUT touching the DB."
    required: false
---

Runs the **sanitize / data retention** routine on the Che state store. Intended to keep the SQLite index small, fast, and exportable within the `--include-db` size budget. **Single source of truth remains the filesystem (MD/JSONL files):** anything purged from the DB can be re-materialized at any time via `che state rebuild-index`.

**Agent action:**
1. Resolve worktree from binding or user input.
2. FIRST RUN ALWAYS `--dry-run` unless the user explicitly typed `--apply` / "aplicar" / "yes I want to delete". Show the user:
   - `decisions_old`: número de decisions mais velhas que max-age-days a ser purgadas
   - `decisions_over_cap`: número de decisions removidas por excesso da cap max-decisions
   - `bindings_old`: non-BOUND bindings expiradas
   - `tasks_done_old`: tasks DONE com updated_at > max-age
   - `db_path`: arquivo afetado
3. If user confirms (or dry-run was not requested because user explicitly said "aplicar sem dry-run"), run:
   ```
   python3 -m che_core.cli state sanitize "$WORKTREE_ROOT" \
     [--max-age-days 180] \
     [--max-decisions 5000] \
     [--dry-run] \
     --json
   ```
4. After a successful run WITH `--dry-run=false` → run one more `python3 -m che_core.cli state query --sql "SELECT count(*) AS c FROM decisions" --worktree-root "$WORKTREE_ROOT" --json` to prove the new counts.

**Safety guarantees:**
- Deletes only from the INDEX (SQLite). Filesystem MD/JSONL files in CHE_PROJECT_DIR / CHE_WORKSPACE_SHARED are **NEVER** touched by this command.
- `VACUUM` is run automatically after sanitize to reclaim free pages so the DB file shrinks.
