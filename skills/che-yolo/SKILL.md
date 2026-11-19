---
name: "che-yolo"
description: "End-to-end autonomous delivery from an Approved SPEC: che-act with REVIEW_MODE=FINAL (one commit per vertical slice), manual test plan gate, che-ship with all 5 executable gates enforced, manual test execution with evidence, PR evidence comment and ready-for-review. Stops and hands back to the human on any gate block, failed AC, failed app setup, or missing capability. Never merges."
---

# Che — YOLO (end-to-end autonomous delivery)

> What this is: one command that takes an Approved SPEC to a PR marked ready for review.
> Why it matters: it removes the pauses that ask a human to say "continue", not the checks that
> stop a bad change. Read next: `che-act`, `che-ship`, `che-manual-test-executor`. Confidence: high
> on the phase order (each phase is an existing, tested skill); medium on the evidence upload, which
> has no supported `gh` endpoint for images.

> **SHARED REFERENCES (CANONICAL — DO NOT DUPLICATE body here):**
> - Implementation loop, slice commits, review modes: `che-act` skill
> - Ship gates 0.9.1→0.9.5, commits, push, DRAFT PR: `che-ship` skill
> - Executable test contracts: `che-manual-plan` skill + `che manual-plan` CLI
> - Execution and evidence: `che-manual-test-executor` skill
> - Storage boundary and paths: `contracts/path-canonicity-che.md`

## 0. The one human gate

**Entry gate:** an Approved SPEC. **Exit:** a report that says "your turn".
Everything between those two points runs without asking the user to approve a plan, a commit, or a
setup command.

YOLO never lowers a quality bar. It only removes pauses. The table is the whole contract:

| Decision | Normal command | Under YOLO |
| --- | --- | --- |
| SPEC approval | human | **REQUIRED before start** — never auto-approved |
| Task graph approval | human | auto-approved only if the structural checks pass |
| Per-slice review | `REVIEW_MODE=INCREMENTAL` | `REVIEW_MODE=FINAL` |
| Commit plan | human | auto-approved after the blacklist + secret scan |
| Manual test setup | human | auto-run; failure stops the run |
| Ship gates 0.9.1→0.9.5 | enforced | **enforced, never bypassed** |
| Mark PR ready for review | human | automatic, and only when every AC is PASS or HUMAN_REQUIRED |
| Merge | never | **never** |

Record the contract once, before the first write:

```bash
che decision_append "$WORKTREE_ROOT" "YOLO_START" "spec=${SPEC_PATH} review_mode=FINAL qa=${QA_PROFILE} max_slices=${MAX_SLICES} user_optin=explicit"
```

## 0.1 Preconditions (fail fast — never guess)

1. `WORKTREE_ROOT` and `PROJECT_SLUG` confirmed by the user. Missing → ASK.
2. `SESSION_ID` resolved, then the storage preflight:

```bash
che compute_paths "$WORKTREE_ROOT" "$SESSION_ID" --cwd "$PWD"
che ensure_dirs "$WORKTREE_ROOT" "$SESSION_ID" --cwd "$PWD"
che assert_outside_worktree "$CHE_SESSION_DIR" "$WORKTREE_ROOT" --label "CHE_SESSION_DIR (yolo evidence)"
```

   Read the printed `KEY=VALUE` pairs and keep them in context. Do **not** use `eval` or `export`:
   on PowerShell the equivalent is `$env:KEY = "value"`.
3. **Approved SPEC.** Resolve `SPEC_PATH` from the argument, else the newest file under
   `$CHE_WORKSPACE_SHARED/specs/**/*.md`. Run `che spec validate "$SPEC_PATH" --json` and read the
   frontmatter `status`. Anything other than `Approved` → **STOP** and offer `/che-spec`. This is the
   only place YOLO refuses to proceed autonomously.
4. `gh auth status` succeeds.
5. Capability probe: one read-only `list_pages` call (browser) and `git --version` (terminal). Record
   the result; a missing browser degrades `ui` ACs to `BLOCKED`, it does not crash the run.
6. Branch is not the default branch. On the default branch → STOP and ask for a feature branch.

## 0.2 Phase A — Implement (`che-act`, REVIEW_MODE=FINAL)

Invoke `che-act` with `SPEC_PATH`, `WORKTREE_ROOT`, `PROJECT_SLUG`, `SLUG`, and
`REVIEW_MODE=FINAL` (persisted in `task_graph.md` and via `REVIEW_MODE_SET`).

Auto-answer the interactive gates **only** when the structural checks pass:

| Gate | Auto-answer | Condition to auto-answer |
| --- | --- | --- |
| Task graph approval (§1.2) | `A` | F0 is row T1, every task touches ≥2 layers or has `-H-OVERRIDE-`, no horizontal stack |
| Test spec smoke (§1.5) | `A` | 5 mandatory bullets present |
| Slice review (§2.2.2) | skip | `REVIEW_MODE=FINAL` — the gate does not fire |
| `che-pair` per slice | still runs | a FAIL blocks that slice; never auto-waived |

Slice discipline is unchanged: **one vertical slice = one commit**, tests in the same commit,
`che test-lock` honoured when `TEST_FREEZE=ON`, no planning artifact staged.

Stop Phase A immediately when: a slice fails its tests twice, `che-pair` reports a CRITICAL, the
slice would leave the TASK ENVELOPE blast radius, or the slice count exceeds `MAX_SLICES` (default 8).
Log and hand back — do not "push through" a red slice.

## 0.3 Phase B — Manual test plan gate

The plan is a contract, not prose. It must exist and validate **before** ship, because the PR body
quotes it.

```bash
che manual-plan sync "$WORKTREE_ROOT"
che manual-plan validate "$PLAN_PATH"
```

- Exit 0 → continue.
- Failure → invoke `che-manual-plan` once to fill the missing executable blocks, then re-validate.
- Second failure → **STOP**. A plan that cannot be executed is a planning defect, not a reason to
  improvise the test run.

## 0.4 Phase C — Ship (`che-ship`)

Invoke `che-ship` with `WORKTREE_ROOT`, `PROJECT_SLUG`, `SLUG` and the QA profile.

- Auto-approve the numbered commit plan. Before that approval, the blacklist and secret scans still
  run; a hit blocks.
- Gates 0.9.1→0.9.5 run in their canonical order. **YOLO adds no bypass.** Any 🔴 verdict stops the
  run and hands back with the report path.
- Capture `PR_URL` from the created DRAFT PR. If the user explicitly requested a gh-stack in this
  session, capture every layer PR bottom-up and treat the **top** layer as the evidence target.
  Otherwise there is exactly one PR.

Log each completed phase:

```bash
che decision_append "$WORKTREE_ROOT" "YOLO_PHASE_DONE" "phase=ship pr=${PR_URL} qa=${QA_PROFILE}"
```

## 0.5 Phase D — Execute the plan (`che-manual-test-executor`)

Invoke the executor with `WORKTREE_ROOT` and `PLAN_PATH`.

- Auto-approve the setup gate (option A). Setup failure → **STOP** and report the command plus the
  last 20 lines; do not invent a base URL.
- Every AC gets a verdict: `PASS`, `PARTIAL`, `FAIL`, `BLOCKED`. Never promote `BLOCKED` to `PASS`.
- Evidence goes to `$CHE_SESSION_DIR/qa/evidence/...` via `che output_path` — never inside the
  worktree, never committed.

## 0.6 Phase E — Publish evidence and mark the PR ready

**Eligibility (all must hold):** every AC is `PASS`, or `PARTIAL` whose only gap is a `manual` step
reported as `HUMAN_REQUIRED`. Any `FAIL` or `BLOCKED` → skip this phase and go to §0.7 with the
blocker list. A PR is never marked ready on unverified behaviour.

1. **Comment.** Build a compact table (one row per AC: id, verdict, evidence kind, relative path) and
   post it:

```bash
gh pr comment "$PR_URL" --body-file "$EVIDENCE_COMMENT"
```

2. **Images.** There is no supported `gh` endpoint that uploads an image into a PR comment. Attempt an
   inline embed **only** when the evidence already has a public URL (CI artifact, repo-hosted asset).
   Never fabricate a URL and never commit screenshots into the repository. Otherwise assemble a
   paste-ready folder:

   - `$CHE_SESSION_DIR/qa/evidence/pr-<number>-upload/` — the screenshots, video and logs;
   - `EVIDENCE.md` inside it — the same AC table, ready to paste into the PR;
   - the comment says: `Screenshots: <n> files in <absolute path> — attach manually.`

3. **Ready for review.** If the user explicitly requested a gh-stack, mark every layer bottom-up;
   otherwise mark the single PR:

```bash
gh pr ready "$PR_URL"
```

```bash
che decision_append "$WORKTREE_ROOT" "YOLO_EVIDENCE" "pr=${PR_URL} acs_total=${N} pass=${P} partial=${Q} fail=${F} blocked=${B} upload_folder=${UPLOAD_DIR:-none}"
```

## 0.7 Phase F — Report and hand back

Always the last step, whether the run completed or stopped. One block, no diff dump:

```markdown
| YOLO | <COMPLETE | STOPPED at phase X> |
| SPEC | <path> — Approved |
| Slices | <n> implemented · <m> commits |
| PR | <PR_URL> — <DRAFT | READY FOR REVIEW> |
| Gates | scope <score> · review <0C/xH> · compliance <0C/0H> · qa <profile/status> · domain <slug/skipped> |
| Test plan | <p> PASS · <q> PARTIAL · <f> FAIL · <b> BLOCKED |
| Evidence | <comment URL or upload folder> |
| Blockers | <1 line each, or "none"> |
| Your turn | <the single decision you must make next> |
```

Close with `che decision_append "$WORKTREE_ROOT" "YOLO_COMPLETE" "status=<COMPLETE|STOPPED> phase=<X> pr=<URL>"`.

## 1. Stop conditions (YOLO ends, human is called)

| Condition | Phase | What the report must contain |
| --- | --- | --- |
| SPEC missing, Draft or invalid | A | The `che spec validate` failures + the `/che-spec` offer |
| Structural task-graph violation (F0, vertical slicing, horizontal stack) | A | The offending rows |
| Slice red twice, `che-pair` CRITICAL, blast-radius breach | A | Slice id, test output tail, files |
| `MAX_SLICES` exceeded | A | Actual count and the split proposal |
| Manual plan invalid after one repair | B | The `MP-` failures |
| Any ship gate 🔴 | C | Gate id, report path, top findings |
| Push / PR creation failure | C | Command, exit code, remote message |
| App setup failure | D | Command and the last 20 lines |
| Any AC `FAIL` or `BLOCKED` | D | AC ids and evidence paths |

## 2. What YOLO never does

- Never approves or edits a SPEC.
- Never skips, softens or overrides a ship gate, a secret scan, or the worktree binding check.
- Never merges, force-pushes, or rewrites existing slice commits.
- Never marks a PR ready with a `FAIL` or `BLOCKED` AC.
- Never commits evidence, reports, specs, task graphs or decision logs into the repository.
- Never invents a test result, a URL, or a capability it could not probe.

## 3. Windows and shell portability

- Only `che`, `gh` and `git` are required. No `grep`, `sed`, `awk`, `date`, `tee` or `find` in any
  command — the same instructions run in PowerShell, CMD, bash and zsh.
- Resolve every path with `che output_path` / `che compute_paths`; never concatenate path separators
  by hand.
- Environment variables: `export` on bash/zsh, `$env:NAME = "value"` on PowerShell. Never `eval`.
- Browser evidence needs the Chrome DevTools MCP. Without it, `ui` ACs are `BLOCKED` (reported, never
  guessed) and §0.6 is skipped.
- `gh pr comment`, `gh pr ready`, `git push` and `che` behave identically on Windows; no POSIX-only
  flag is used.
