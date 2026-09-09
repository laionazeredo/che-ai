# Domain: `engineering` · Mandatory Playbook (no skipping steps)

Feature and bugfix development pipeline. **DO NOT SKIP STEPS.** Always complete = painless shipping.

---

## Stage 0: Spec Approved & Bounded Context (SM gates 0→1.5)
Mandatory input: Approved SPEC with YAML frontmatter (domain = engineering by default).
Sub-stages (all performed by Scrum Master §0→1.5, NOT by developer):
- **0.0 F0 Tracer Bullet Defined & Stamped Complete (CANONICAL #0 — NON-NEGOTIABLE):**
  1. Read Approved SPEC §4.5 VERTICAL SLICES table. Extract row F0 (first line). If SPEC has no §4.5 or no F0 row → STOP. Require user: "(A) Run /che-spec and add VERTICAL SLICES §4.5 with F0 Tracer / (B) Add EXPLICIT_OVERRIDE_HORIZONTAL_PLAN literal with ≤120 chars justification + log decision".
  2. From F0 row extract: (a) `F0_BIDS` = list B-IDs covered, (b) `F0_LAYERS` = distinct count Layers Touched (MUST be ≥2) or literal "override", (c) `F0_DONE` = DONE criterion observable string.
  3. Output stamped variable: `F0_STAMP = PENDING` at stage start.
  4. **F0 must be 100% COMPLETE (all tests green · DONE criterion verifiable) BEFORE any F1/F2/FN task is UNBLOCKED in task-graph.** If any F1+ task has `Depends on = []` (no blockers) while `F0_STAMP != COMPLETE` → 🔴 INVALID task-graph, reorder Kahn to make F1..FN depend on T1=F0.
  5. Transition rule: When che-qa reports 100% ACs PASS for T1=F0 → set `F0_STAMP = COMPLETE` (log event `[F0-TRACER-COMPLETE] spec=<slug> layers=<count> bids=<N>` via decisions helper). Only after T1 stamp are downstream tasks eligible for parallel dispatch.
- 0.1 2-level binding approved (workspace + worktree).
- 0.2 ADR if `change_class ∈ {arch, platform, large-migration}`.
- 0.3 Topological task graph with atomic envelopes + file locks (where Kahn parallelism applies).
- 0.4 Detected QA stack + compliance light plan.
- 0.5 **GATE Approved**: SPEC stamped Approved **AND F0_STAMP != INVALID**. If either fails, loop back.

Output of this stage: `task_graph.md` + `tasks/<TASK_ID>/envelope.md` for each task + `F0_STAMP = PENDING | COMPLETE` global session state.

---

## Stage 1: TDD Loop (per task)
Canonical flow per atomic task.

| Step | Action | Expected Artifact | Fail condition |
|---|---|---|---|
| 1.1 | **Write FAILING test** representing 1 AC. | `*.{test,spec}.{ts,rs,py}` or Playwright spec | Test does not fail = bad test, rewrite. |
| 1.2 | **Implement** MINIMUM amount of code for test to pass. | Code in `src/` | Test still fails → back to 1.2. |
| 1.3 | **Refactor** now that test is green: rename variables, extract function, improve types. **DO NOT change behaviour.** | Clean code. | Test no longer green → bad refactor, undo. |
| 1.4 | **Repeat** for next AC. | — | All task ACs covered by test. |

### Stage 1 Hard Fail Rules
- ❌ Implemented before failing test = stage fail. Go back.
- ❌ Empty test (mock everything, empty assertion `expect(true).toBe(true)`) = fail.
- ❌ Happy path only testing. Test must cover at least 1 error path per AC.

---

## Stage 2: Quality Gates (G-ENG-1 + G-ENG-2 mandatory)
**Automatically run by ship §0.9.5 DOMAIN GATES** before opening Draft PR.

| Gate ID | Name | Mandatory Numerical Threshold (per S14 CHE_RULES §X Engineering Gates) | Auto-retry | Human required after |
|---|---|---|---|---|
| G-ENG-1 | **Lint · Typecheck · Test Pass Rate** | `lint_errors=0`, `typecheck_errors=0`, `test_pass_rate=100%` (0 tests can FAIL) — per S14. Warnings allowed if `--exact=false`. | 1 auto-retry if flaky detected (same seed 2x runs) | 2nd failure |
| G-ENG-2 | **Coverage Gate** | `lines_coverage ≥ 70%` GLOBAL + `new_code ≥ 80%` + `branch_coverage ≥ 65%` — all per S14. Excludes `**/*.test.*`, `**/migrations/**`, `**/*.config.*`. | 1 auto-retry rerun coverage report. | 2nd failure (threshold only lowered via logged user EXPLICIT_OVERRIDE). |

### Override rules (same as ship §0.9.5):
- 1st FAIL on any gate → agent applies 1 free retry with top-3 deviation suggestions.
- 2nd FAIL → HARD STOP. 3 options: (A) manual fix (B) logged user VERBATIM EXPLICIT_OVERRIDE (C) cancel ship.
- **Threshold NEVER LOWERED BY AGENT.** Even if it "looks ok".

---

## Stage 3: Dev Handoff for Code Review
Checklist 100% filled BEFORE opening PR.

| # | Item | Confirmed? |
|---|---|---|
| 1 | Conventional commit message `feat|fix|refactor|chore|docs|perf|ops(scope): <description>` in EN | |
| 2 | All ACs in SPEC marked DELIVERED + evidence (green test link or Playwright screenshot) | |
| 3 | Migrations: corresponding DOWN added if reversible, else justified in comment | |
| 4 | New ENV vars: all declared in `.env.example` + zod parser in `@flockr/config` or equivalent | |
| 5 | Gates G-ENG-1 and G-ENG-2 PASSED + report artifacts attached to PR description | |
| 6 | Secrets / PATs / keys: `git diff --cached` confirms NO tracked secret | |
| 7 | Local `typecheck` + `lint` command passes 100% clean before push | |
| 8 | PII logging redacted + trace_id correctly propagated | |
| 9 | Decisions.log updated with non-trivial architectural decisions | |
| 10 | PR Description contains: What changed? Why? How to test? Risks? Rollback? | |

---

## Stage 4: Post-deploy (when applicable) — §20 FIRE DRILL
| Action | Deadline | Artifact |
|---|---|---|
| 4.1 SLO baseline check (p50, p95, p99 latency / error rate) | 5 min after visible deploy | Screenshot or logged metric |
| 4.2 Rollback capability: confirm documented and tested rollback command (staging). | Before prod deploy | rollback runbook |
| 4.3 Sentry / observability provider: new errors? (no = ok. yes = rollback or hotfix). | 10 min after deploy | alert check |
| 4.4 decisions.log POST_DEPLOY_CHECK entry: `timestamp + commit + env + who + result = {ok,warn,rollback}` | Immediately | decisions.log |

---

## Mandatory Decision Log per Stage
Each non-trivial stage → 1 line in `decisions.log.jsonl` (official helper):
```
[0-STAGE-APPROVED] spec=<slug> approved domain=engineering
[1-TDD-LOOP-DONE] task=<TASK_ID> ac_count=N test_count=N pass_rate=100%
[2-GATES] gate=G-ENG-1 pass=yes gate=G-ENG-2 pass=yes
[3-HANDOFF-READY] pr_url=<draft> checklist_completed=10/10
[4-POST-DEPLOY-CHECK] env=production result=ok
```
