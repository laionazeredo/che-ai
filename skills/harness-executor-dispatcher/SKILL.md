---
name: "harness-executor-dispatcher"
description: "Parallel batch executor for the harness. Given a TASK GRAPH, builds topological batches, enforces blast-radius file-lock partitions, fans-out independent harness-developer instances in parallel, runs per-batch MERGE AUDIT + scope/QA/compliance gates, and produces a BATCH_REPORT. Invoked BY harness-scrum-master only when task_graph.md has >=2 tasks with no dependencies sharing zero files. Or explicitly by /harness-parallel."
---

# Harness — Parallel Executor Dispatcher

This skill is the **parallel execution backbone** of the harness.
It takes a `task_graph.md` (from Scrum Master) + one task envelope per task,
performs **Kahn's topological sort by dependency + file-lock blast-radius partition**,
fans out `harness-developer` calls as parallel independent sub-agent calls in BATCHES,
then runs per-task gates (scope/QA/compliance-light) and a per-batch **MERGE AUDIT** to catch
cross-task file conflicts BEFORE the next batch starts.

**CRITICAL CONTRACT**: This skill is called BY `harness-scrum-master`. It is **NOT** a top-level
orchestrator — SM retains authority over scope + overall gates. This skill only does dispatch.

---

## 0. Preconditions (MANDATORY — fail immediately)

The SM MUST pass, either as function arguments or in a well-known dispatch config file:

| Input | Source | Purpose |
|---|---|---|
| `WORKTREE_ROOT` | Confirmed by SM preflight | Absolute path |
| `$HARNESS_WORKSPACE_SHARED/task_graph.md` (DURÁVEL workspace-shared) | SM Phase 0 output | Full task list, deps, status |
| One `task_envelope_<TASK_ID>.md` file per task in `TODO`/`READY` state → at `$HARNESS_WORKSPACE_SHARED/tasks/<TASK_ID>/` (DURÁVEL) | SM Section 2.1 output | Each one has **Blast Radius → ALLOWED files** |
| `max_parallel` (optional, int) | SM or user | Cap for concurrent Devs. Default = `min(cpu_cores, 3)`. Max cap = 4 hard. |

If ANY task marked READY-for-parallel does NOT have a fully enumerated `Blast Radius → ALLOWED files` list (with globs resolved to concrete files, not just "src/*") → **REFUSE parallel for that task and fall back to serial.** Blast-radius glob wildcards are not allowed in parallel mode because the lock system cannot validate intent.

---

## 1. Step 1 — Validation + Topological Batching

### 1.1 Ingest task_graph.md

Parse:
- All rows from the `Task Table`.
- For each row: `ID`, `Depends_on[]`, `Status`.

### 1.2 Kahn's topological sort to get READY batches

A "READY" task = all tasks in `Depends_on[]` have `Status == DONE`.

Algorithm:
1. Let `in_degree[T] = len(Depends_on[T] not DONE)` for all T.
2. `queue = [ T where in_degree[T] == 0 and Status == TODO ]`.
3. While queue not empty:
   - `batch_candidates = queue`  (all zero-in-degree currently) → this is **Batch N**.
   - Apply **Blast-Radius File Partition** (next step) on `batch_candidates`.
   - If partitioning reduces the batch → remainder go back to queue as "READY-for-next-batch-within-phase"; they'll run in mini-batch **after** current mini-batch finishes + merge audit passes (still before advancing in-degree to next Kahn's wave).
4. Mark batch as complete after all tasks + merge audit pass.
5. Reduce in-degrees for successors. Repeat.

### 1.3 Blast-Radius File-Partition (the critical correctness guard)

Given a candidate set `S = {T1, T2, ...}` from the same Kahn wave:

1. For each task `T` in `S`, extract the **EXPLICIT** file list from `task_envelope_<T>.md` → section `Blast Radius → ALLOWED`. Call this `Files(T)`.
2. Build an **intersection conflict graph** where tasks are vertices and an edge `T1—T2` means `Files(T1) ∩ Files(T2) != ∅`.
3. Run a **greedy graph coloring** on the conflict graph (colors = mini-batches). Tasks of the SAME color = NO pairwise file conflict → safe parallel.
4. Each color = one **mini-batch**. Mini-batches are run SERIALLY within the same Kahn wave (they share files), but tasks INSIDE one mini-batch run PARALLEL (no shared files).

**This gives us correctness even if T2 and T1 both want to edit `utils.ts` — they will be split into different mini-batches automatically, so T1 writes, merges, then T2 reads updated + writes.**

### 1.4 Output of Step 1

Save to `$HARNESS_WORKSPACE_SHARED/execution_batches.md` (DURÁVEL workspace-shared, via `source "${HARNESS_HOME:-$HOME/.trae}/contracts/harness_sessions_contract.sh"`):

```markdown
# EXECUTION BATCHES — <task-id>

## Strategy
- algorithm: Kahn topological sort + greedy graph coloring on file-conflict graph
- max_parallel: <N>
- batches_count: <B>

## Batch B1 (Kahn wave 1, mini-batch 1/2, parallel-safe, files pairwise disjoint)
| Task | Depends on | Files (count) | Status |
|---|---|---|---|
| T1 | - | 7 files | READY |
| T3 | - | 3 files | READY |

## Batch B1b (Kahn wave 1, mini-batch 2/2, serial fallback, conflict with B1 on src/lib/utils.ts)
| Task | Depends on | Files sharing reason | Status |
|---|---|---|---|
| T2 | - | utils.ts overlaps T1 | QUEUED |

## Batch B2 (Kahn wave 2, depends on B1+B1b DONE)
...
```

---

## 2. Step 2 — File Lock System

For every mini-batch about to run:

1. Before fanning out Devs:
   - For each task T in the mini-batch, for each file f in Files(T):
     - **ASSERT**: no `$HARNESS_WORKSPACE_SHARED/_locks/<normalized-f>.lock.json` exists with state `HELD`.
     - If any exists held → re-queue T into next mini-batch.
2. On task T start (just before invoking harness-developer):
   - Atomically for ALL files in Files(T):
     - Write `$HARNESS_WORKSPACE_SHARED/_locks/<hash>-<basename>.lock.json` (DURÁVEL workspace-shared, runtime, never staged):
       ```json
       {"task_id": "T1", "batch": "B1", "held_at": "<ISO>", "state": "HELD"}
       ```
   - If atomic acquisition fails → rollback + re-queue to next mini-batch.
3. On task T end (regardless of success/failure):
   - Atomically for ALL files in Files(T): change state `RELEASED` with `ended_at` + `outcome` (PASS/FAIL_SCOPE/FAIL_QA/FAIL_COMPLIANCE).

Lock directory is `$HARNESS_WORKSPACE_SHARED/_locks/` → lives OUTSIDE user worktree code by design (MORATÓRIA §19.1); never staged/committed.

---

## 3. Step 3 — Fan-Out: Parallel Developer Calls

For each task T in current mini-batch:

1. Mark `task_graph.md` row for T: `Status = IN_PROGRESS (parallel, batch=<B>, mini-batch=<MB>)`.
2. Invoke a **dedicated parallel-execution sub-agent call** for `harness-developer` with:
   - Full env variable context: `WORKTREE_ROOT`, TASK_ID=T, envelope path.
   - `general_purpose_task` sub-agent invoked with **isolation semantics** — each agent writes its own report file as `$HARNESS_SESSION_DIR/reports/dev_report_<TASK_ID>_<timestamp>.md` (EFÊMERO per-session, via contract) and **never writes to task_graph.md** (that is dispatcher's single-writer role).
   - Output: when all sub-agents return, collect all per-task dev reports.

### 3.1 Developer Report Per-Task Parallel Contract

Every parallel Dev MUST return a machine-readable section:
```
## PARALLEL_WRITES (for dispatcher merge-audit)
Files modified: /absolute/path/a.ts, /absolute/path/b.ts, ...
```
If absent → dispatcher treats the task as FAILED_SCOPE (contract not upheld), rejects + re-runs serial (not parallel).

---

## 4. Step 4 — Per-Task Gates (parallel, per-task but SM-validated)

Once ALL tasks in mini-batch have returned a Dev report:

1. **For EACH task T in mini-batch, SERIALLY** (SM is still single-writer for gates + task_graph, because QA/compliance scan worktree state which is shared):
   - Scope Validation (harness-scrum-master rules section 2.3).
   - If PASS → mark `SCOPE_OK`.
   - Run QA (harness-qa) on task T.
   - If PASS → mark `QA_OK`.
   - Run Compliance LIGHT (harness-compliance, per-task).
   - If PASS → mark `DONE`.
   - If any gate fails → mark FAILED_*, stop advancing this task; do NOT release locks (they remain `RELEASED_FAILED` so next re-run forces overwrite caution); this task goes back SM flow.
2. Per-task failures do **NOT** block other tasks of the same mini-batch (they passed gates independently). But they DO block dependent tasks in next Kahn wave.

### 4.1 MERGE AUDIT (cross-task within same mini-batch)

Before moving to the next mini-batch or next Kahn wave:

Algorithm:
1. Collect every file in every `PARALLEL_WRITES` list from tasks in this mini-batch.
2. Build frequency map.
3. **Any file with frequency > 1 written by different tasks in THIS mini-batch → FLAG CONFLICT.**
4. Conflict severity:
   - `LOW`: different files in same directory (no overlap, just coincidence) → ok.
   - `MEDIUM`: exact same file path but diff is disjoint (hunks don't overlap) → SM reviews, applies with explicit decision.log entry.
   - `HIGH`: exact same file path AND overlapping hunks (or the file is > 100 lines modified by both) → **HARD FAIL.** Roll back one of the two task's changes (git stash or git checkout HEAD -- <file> for whichever has more LOC committed), re-run task serial, re-apply gates.
5. Save merge-audit report to `$HARNESS_SESSION_DIR/reports/merge_audit_<BATCH>_<MINI>.md` (EFÊMERO per-session).

If ANY task fails gates OR merge audit reports HIGH conflict → mark mini-batch PARTIAL and continue. The dispatcher returns a structured status to SM.

---

## 5. Step 5 — Loop, Batch Complete, Return

1. Once mini-batch passes gates + merge audit → release HELD locks → `rm` lock files.
2. Advance Kahn in-degree counter by 1 for each task that is DONE.
3. Build the next mini-batch or next Kahn wave.
4. When **no more tasks remain** (all in task_graph marked DONE or FAILED_*):
   - Write `$HARNESS_SESSION_DIR/reports/BATCH_EXECUTION_REPORT.md` (EFÊMERO per-session, via contract)
     - Batches run, minibatches, tasks per batch, conflicts caught
     - Per-task status (DONE / FAIL_SCOPE / FAIL_QA / FAIL_COMPLIANCE / CONFLICT_ROLLBACK)
     - Per-batch merge audit tally
     - Wall-clock approx
     - Lock contention count
   - Return structured summary to `harness-scrum-master`.
   - SM then proceeds to **Compliance HEAVY → manual_test_plan → final_summary** as usual (no parallelism in final stage; it's a single cross-cut pass).

---

## 6. When to REFUSE parallelism (FALL BACK to serial)

Safety first. The dispatcher MUST fall back to SM's serial per-task loop if ANY:

1. Any task in current candidate set does NOT have a full, enumerated (non-glob) file list.
2. Conflict graph coloring produces > `len(S)` colors (fully serial, no parallel wins) → just use serial.
3. `max_parallel == 1` set by user.
4. User explicitly requests `--serial` flag.
5. Worktree has uncommitted dirty changes outside harness scope (risk of interleaving non-harness edits).
6. A lock file from PREVIOUS aborted session exists → present to user with list; ask "purge stale locks and proceed?" or abort.

**Rule: parallelism is an OPTIMIZATION, never a REQUIRED path.** Correctness beats speed 100% of the time.

---

## 7. Never-Dos

- NEVER have two tasks in the same mini-batch sharing files. If this somehow slips (race on lock acquisition) → merge audit catches and rolls back. This is defense-in-depth.
- NEVER let a parallel Dev write directly to `task_graph.md`. Single writer = dispatcher/SM.
- NEVER run Compliance HEAVY (final sweep) or the HEAVY cross-file checks in parallel; they scan the entire cumulative diff and are single-pass.
- NEVER trust a task that doesn't emit `PARALLEL_WRITES`. Refuse its output.
- NEVER allow > 4 parallel Devs. Context window + reasoning cost grows O(n).

---

## Appendix A: Configuration Defaults

```yaml
max_parallel_default: 3
max_parallel_hard_cap: 4
lock_dir: $HARNESS_WORKSPACE_SHARED/_locks  (DURÁVEL workspace-shared, outside user worktree)
stale_lock_timeout_seconds: 3600
merge_audit_high_conflict_min_lines_overlap: 5
```

User can override via file: `$HARNESS_WORKSPACE_SHARED/tasks/<task-id>/dispatcher.config.json` (DURÁVEL, per-task, shared across sessions) on a per-task basis.
