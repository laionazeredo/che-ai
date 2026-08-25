---
description: "Explicit parallel execution mode. ERROR if not parallelizable (no serial fallback — parallel-or-bust)."
arguments:
  - name: worktree
    description: "Absolute worktree path. If missing, ASK first."
    required: false
  - name: max-parallel
    description: "Override concurrency cap (1-4). Default 3; >4 clamps to 4 + warning."
    required: false
  - name: serial
    description: "Force sequential (one task at a time) — for debugging."
    required: false
  - name: purge-stale-locks
    description: "Auto-purge .trae/_locks/*.lock.json from aborted runs (asks confirm unless flag set)."
    required: false
---

IMMEDIATELY invoke **`harness-scrum-master`** Skill with `force_parallel=true`.

Preflight:
1. If worktree missing → ASK.
2. If any task envelope Blast Radius still has globs (no explicit file list) → ERROR. User MUST enumerate files — NO serial fallback (parallel-or-bust when command is explicitly /harness-parallel).
3. Then invoke **`harness-executor-dispatcher`** to fan out.
