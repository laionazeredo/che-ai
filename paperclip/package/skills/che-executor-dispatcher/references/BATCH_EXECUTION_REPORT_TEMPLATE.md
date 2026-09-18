# BATCH EXECUTION REPORT — <task-id>

> Written on completion of ALL batches by che-executor-dispatcher.
> SM uses this to decide whether to proceed to Compliance HEAVY, or to re-run failed tasks.

## Summary

| Metric | Value |
|---|---|
| total tasks | N |
| DONE | k |
| FAIL_SCOPE | a |
| FAIL_QA | b |
| FAIL_COMPLIANCE_LIGHT | c |
| CONFLICT_ROLLBACK (merge audit HIGH) | d |
| refused_parallel_fallback_serial | e |
| total wall-clock (approx seconds) | S |
| batches total | B |
| minibatches total | MB |
| lock contention events | L |

## Per-Task Final Status

| Task ID | Batch | Run Mode (parallel / serial-fallback) | Final Status | Gate failures (if any) |
|---|---|---|---|---|
| T1 | B1 | parallel | DONE | — |
| T2 | B1b | serial-fallback | FAIL_SCOPE | missing AC 2.3 |
| T3 | B2 | parallel | FAIL_QA | typecheck fail: src/x.ts:42 |

## Merge Audit Per-Batch Tally

| Batch | LOW | MEDIUM | HIGH (rollback) | Actions taken |
|---|---|---|---|---|
| B1 | 0 | 0 | 0 | — |
| B2 | 0 | 1 | 1 | Rolled T5 writes to `shared.ts`, re-run serial |

## Refusals / Fallbacks

- Tasks refused parallel (glob or non-enumerated file lists in envelope): <list>
- Tasks serial-fallback due to file conflict coloring: <list>

## Remaining Blocked Tasks

If any task failed, list all dependent tasks and why blocked:
| Task | Depends on failed task | How to unblock |
|---|---|---|
| T6 | T3 FAIL_QA | fix T3 typecheck fail → rerun T3 gates → T6 READY |

## Handoff to Scrum Master

- If FAIL + CONFLICT columns are ALL zero → SM proceeds to:
  1. Compliance HEAVY (single-threaded, not parallel)
  2. Generate manual_test_plan.md
  3. Generate final_summary.md
  4. Report to user
- If any FAIL → SM re-queues failed tasks in serial mode one by one, or asks user for direction.
