# 🌍 Che — Global Slash Commands Reference

These are slash commands the user can type in the chat to interact with the che.
The agent MUST recognise these and react immediately.

> Convention: `/che-*` commands are global and work on ANY repo / worktree.
> All commands first validate: "is the worktree confirmed?" If not, block and ask for worktree path.

---

## 🏗 ARCHITECTURE: Commands vs Skills (CANONICAL — TOP LEVEL — DO NOT DUPLICATE)

> **Conceptual difference:** Commands = UX entry point (slash `/che-X`) ↔ Skills = content/executor of work.
> DO NOT turn ALL commands into skills. The separation below is intentional (KISS).

### Category A — 22 "heavy" commands = PREFLIGHT VALIDATION WRAPPER → invoke corresponding Skill / CLI module:
| Command | Skill / module | Why separate wrapper? |
|---|---|---|
| `/che-architect` | `che-architect` | Strategic system design: stack, infra, security, compliance, accessibility, and operations. |
| `/che-archeology` | `che-archeology` | Infers project Intent and Roadmap from git history and merged PRs. |
| `/che-xray [worktree]` | `che-xray` | Scans tech stack, structure, and patterns. |
| `/che-onboarding [worktree]` | `che-onboarding` | Interactive Product & Architecture context capture. |
| `/che-spec [input] [worktree] [slug]` | `che-spec` | §19 binding preflight (confirmed worktree + level 2 created) → skill generates/validates SPEC in $CHE_WORKSPACE_SHARED. 4 input sources. Approved gate. **DOES NOT depend on /che-act — runs alone.** |
| `/che-plan [worktree] [slug]` | `che-plan` | Preflight SPEC Approved → skill transforms spec into Jira/Linear/ClickUp tickets with BDD ACs. |
| `/che-act` | `che-act` | Worktree preflight → skill executes §0.5 SPEC GATE (auto-invokes che-spec if none Approved) → scope capture + TASK GRAPH. |
| `/che-parallel` | `che-act` → `che-executor-dispatcher` | Worktree preflight + force_parallel flag + error if not parallelisable. |
| `/che-ship` | `che-ship` | Worktree preflight + `gh auth` + no-secret-staged check → skill commits/push/PR. |
| `/che-fix` | `che-debugger-bugfix` | Worktree preflight + capture 4 required inputs → skill runs scientific debug loop. |
| `/che-review` | `che-code-review` | Preflight `gh auth` + parseable PR URL → skill pulls diff + metadata + 4-category review. |
| `/che-diff` | `che-diff-context` | Worktree preflight (Mode B) / gh auth (Mode A) → lightweight CONTEXT report for diff conversation (PR URL or local worktree vs default branch). DIFFERENT from /che-review (blocking review vs context). |
| `/che-manual-test` | `che-manual-test-executor` | Worktree preflight + §19 session binding + finds manual_test_plan.md via --task-id or --plan-path → mandatory setup approval GATE → executes steps via Playwright MCP + screenshot evidence + final 8-section report. DIFFERENT from /che-qa (QA = only automated build/lint/test commands; Manual = step-by-step browser with evidence). |
| `/che-pr-comments` | `che-pr-comments` | Preflight `gh auth` + PR URL → skill downloads comments + classification + triage. |
| `/che-ci-fix` | `che-ci-fixer` | Preflight `gh auth` + worktree → skill classifies R1-R9 + applies minimal fix. |
| `/che-design` / `/che-figma` | `che-social-ui-designer` | Asks mode (A Social Media / B UI-UX / C Design System) + file save path → skill uses open-pencil MCP to build everything locally. |
| `/che-export [--include-db] [--db-size-limit-mb=N]` | `che_core.portability` | Exports project durable data (L2+L3) to a portable archive. **NEW: optional `--include-db` flag includes SQLite state+rag databases if size <= limit (default 250MB). |
| `/che-import [--include-db]` | `che_core.portability` | Imports project durable data from an archive, resolving conflicts. **NEW: optional `--include-db` flag also restores SQLite databases (conflict = suffix `--import-<timestamp>`). |
| `/che-task [list|show|resume|set-status|graph-summary]` | `che_core.task_engine` | Multi-domain task graph picker + ACTIVE_TASK_ID bind in registry + recommends downstream command (che-act / che-design / che-spec) by task envelope domain. |
| `/che-config [--lang-chat=...] [--lang-docs=...] [--lang-report=...] [--pt-check=...]` | `che_core.cli config` | **NEW:** Set session configuration flags (chat language, docs language, PT detection). |
| `/che-workspace [add|list|remove|restore|trash-list]` | `che_core.workspaces` | **NEW:** Manages L1 workspaces (`~/.che-workspaces/workspaces/<slug>/`). |
| `/che-project [init|list|remove|restore]` | `che_core.workspaces` | **NEW:** Initializes L2 project within workspace. |
| `/che-eject [plan|trash-list|restore]` | `che_core.eject` | **NEW:** Ejects Che safely and reversibly. Detects install_kind (git-clone / copy-install), uninstalls adapters via official scripts, moves whitelist to `.trash/che-eject/` (never rm), cleans client `.gitignore` snippets + restore. 3 mandatory safety gates: `--dry-run default`, `--confirmed`, `--i-know-what-im-doing`. Absolute blacklist: `user_rules/`, `bindings/registry.jsonl`, `memory/`, `.git/`, `node_modules/`. |
| `/che-query --sql "..." [--bind ...] [--force]` | `che_core.state_store` | Parameterized SQL query in SQLite state store. Default READ ONLY (SELECT / EXPLAIN / PRAGMA). Needs explicit `--force` for writes. |
| `/che-sanitize [--max-age-days=N] [--max-decisions=N] [--dry-run]` | `che_core.state_store` | Sanitize state store: purge old decisions/bindings/sessions + VACUUM. **MANDATORY `--dry-run` default** before effective (flag only passes on 2nd command without dry-run. **Filesystem SSOT INTACT**: reversible purge via `rebuild-index`. |
| `/che-search "..." [--top-k=N] [--scope=all\|tasks\|specs\|decisions\|envelopes]` | `che_core.state_store` | Full-text search FTS5 + BM25 ranking. Pre-flight: rebuild if DB older than decisions.log mtime. |
| `/che-rag [build-index|search] [--provider=auto\|none\|openai\|st] [--top-k=N] [--no-hybrid]` | `che_core.rag` | Hybrid RAG BM25(40%) + vector(60%). Incremental build by chunk hash. OPTIONAL sqlite-vec. `none` zero-dep fallback ALWAYS works without pip install. |

### Category B — 5 "light" commands = lightweight inline (5 lines to read/write markdown) → **DO NOT become skills (KISS)**:
| Command | Inline implementation | Why NOT a skill? |
|---|---|---|
| `/che-status` | Read `task_graph.md` → count buckets → print status (Portuguese) | Skill would be 10 lines, overhead > value. |
| `/che-skip` | Append `decisions.log.jsonl` (SKIP GATE entry) + mark `task_graph.md` gate as skipped | 3 lines of file writing. |
| `/che-decisions` | Read `decisions.log.jsonl` → summarise (Portuguese) | 2 lines read + summarise. |
| `/che-summary` | Use SM logic to generate interim summary structure | 8 lines summary object assembly. |
| `/che-abort` | Write ABORTED in `session.md` + `task_graph.md` | 2 writes + confirm. |

### Strict rule (KISS):
- If a "light" command DOES NOT exceed ~15 lines of logic → inline.
- If it grows beyond → extract to skill.
- DO NOT create a 5-line skill.

---

## `/che-xray [worktree]`
**What it does:** Scans the repository to identify tech stack, monorepo structure, folder conventions, code patterns, tests, CI, DB, and services. Generates a 12-section `project_profile.md` persisted in the global project registry (Level 1.5).
**When to invoke:** First time Che touches a repo, or to refresh context after significant architectural changes.
**Agent action:** Call `che-xray` skill.

---

## `/che-onboarding [mode:--show|--bootstrap] [worktree]`
**What it does:** Captures durable **human** context: Product Pitch, Personas, Roadmap, Business Logic, and Manual Architecture. Complements `/che-xray`. Stored in `.registry/projects/<slug>/`.
**When to invoke:** After `/che-xray` and before `/che-spec` for new projects.
**Agent action:** Call `che-onboarding` skill.

---

## `/che-architect`
**What it does:** A strategic architecture partner that helps design a complete system from a business idea. Iteratively covers stack, infra, security, compliance, accessibility, localisation, observability, and operations.
**When to invoke:** Before starting a new repository or when refactoring/designing a major new system component.
**Agent action:** Call `che-architect` skill.

---

## `/che-archeology`
**What it does:** Infers the project's strategic backbone (Intent and Roadmap) by analysing git history, merged PRs, and README evolution.
**When to invoke:** When adopting an existing project into the Che framework to establish Specflow alignment.
**Agent action:** Call `che-archeology` skill.

---

## `/che-spec [input_type:ticket|prd-flockr|desc|existing] [input_value] [worktree] [slug]`

**What it does:** Standalone entry-point for generating or validating a **Che Execution Specification (SPEC)** — anti-hallucination/anti-scope-drift planning artifact that replaces legacy Flockr PRD. Saves DURABLE in `$CHE_WORKSPACE_SHARED/spec_<slug>.md` (outside sessions/, outside user worktree). 4 accepted input sources: (A) existing Approved SPEC; (B) Ticket URL (Linear FLO-XXX / ClickUp / GitHub Issue); (C) legacy-project PRD path (.md); (D) brief inline description with iterative prompts.
**When to invoke:** User wants to draft/update a SPEC **before** /che-act, or standalone for planning document, or when SM §0.5 auto-invokes it because no Approved SPEC exists.
**Agent action on this command:**
1. IMMEDIATELY call `che-spec` skill.
2. Preflight: check existing Level 1 binding; if none, ask worktree + create 2-LEVEL binding first.
3. Skill executes 4-source flow → validates §4 7 checks → 1-pass approval loop → atomic temp+mv save.
4. **Returns last 2 parseable lines for SM:**
   ```
   SPEC_PATH=<absolute without quotes>
   SPEC_STATUS=Approved|Draft
   ```
5. Append `[SPEC] <slug> <status> saved at <ISO>` in `$CHE_WORKSPACE_SHARED/decisions.log.jsonl`.
**Syntax examples:**
```
/che-spec input=ticket https://linear.app/flockr/issue/FLO-745 slug=api-fail-closed
/che-spec input=prd-flockr docs/prd/payments/refunds.md slug=refund-flow
/che-spec input=desc slug=fix-qr-scan "QR scanner does not validate already used ticket"
/che-spec input=existing slug=api-fail-closed
```

---

## `/che-plan [worktree] [slug]`
**What it does:** Transforms an Approved SPEC into structured tickets in project management tools (Linear, ClickUp, Jira). Decomposes complex specs into Epics with sub-tasks, goals, and dependency graphs.
**When to invoke:** After `/che-spec` is Approved and before `/che-act` starts, to sync technical plans with the team's project management tool.
**Agent action:** Call `che-plan` skill.

---

## `/che-act [input_type:ticket|prd-flockr|desc] [input_value] [--slug=slug]`

**What it does:** Triggers the full che flow from Phase 0. **SM §0.5 auto-invokes `/che-spec` automatically if no Approved SPEC exists in worktree**, accepting same input args (ticket/prd/desc) and passing them to che-spec.
**When to invoke:** User wants to start implementing a feature/bugfix through the simulated Agile team.
**Agent action on this command:**
1. IMMEDIATELY call `che-act` skill.
2. Scrum Master executes Pre-Flight (worktree path + `che_compute_paths` → ensure_dirs + Level 2 binding).
3. **SM §0.5 SPEC GATE (before scope capture):** Glob `$CHE_WORKSPACE_SHARED/spec_*.md` → parse Approved. If 0 OR user provided input → **automatically invoke che-spec Skill**, passing user input args (ticket/prd/desc).
4. Capture 2 return lines: `SPEC_PATH` + `SPEC_STATUS`. Gate: Approved → releases Scope Capture; Draft → offers (A) `[SPEC-OVERRIDE]` Override logged in decisions / (B) Stop, finish SPEC later via standalone `/che-spec`.
5. Scrum Master proceeds to Scope Capture.
**Syntax examples:**
```
/che-act "Implement Stripe Connect onboarding flow"
/che-act --slug=feat-stripe-connect input=ticket https://linear.app/flockr/issue/FLO-123
/che-act input=prd-flockr docs/prd/stripe-connect.md --slug=feat-stripe-connect
```

---

## `/che-status`

**What it does:** Prints a concise status report of the CURRENT che session.
**When to invoke:** User wants to see where we are in the TASK GRAPH progress.
**Agent action:**
1. Source `"${CHE_HOME:-${HOME}/.che-ai}/contracts/che_sessions_contract.sh"` → `che_compute_paths WORKTREE_ROOT` → look for `task_graph.md` at `$CHE_WORKSPACE_SHARED/task_graph.md` (OUTSIDE worktree).
2. If not found → "No active che session in this worktree. Use `/che-act`."
3. If found → print in Portuguese:
   - Which task is IN_PROGRESS and in which phase (scope/qa/compliance)
   - Counts: Total / TODO / SCOPE_OK / QA_OK / DONE / BLOCKED
   - List of blocked tasks, if any
   - Warnings: tasks near bursting 2 iterations
   - Artifact paths (all OUTSIDE worktree): `$CHE_WORKSPACE_SHARED/` (durable) + `$CHE_SESSION_DIR/` (ephemeral)

---

## `/che-skip <gate> <task-id or "ALL"> <reason>`

**What it does:** Override gate (use with EXTREME CAUTION). Logs the skip with reason and user consent.
**When to invoke:** User explicitly wants to skip a quality/compliance gate (e.g., urgency patch, SM decides scope validation already done manually).
**Valid `<gate>` values (exact):**
- `scope` — skip SM scope validation for a task
- `qa` — skip QA (build/lint/typecheck/tests) stage
- `compliance-light` — skip per-task compliance stage
- `compliance-heavy` — skip FINAL heavy compliance stage (EXTREMELY RISKY — disallow unless user insists TWICE)
**Agent action:**
1. Confirm user wants to skip this gate (ASK if reason was not provided).
2. For `compliance-heavy`: require EXPLICIT confirmation TWICE. Print a huge warning in Portuguese: "This will release without deep security check. Continue anyway?"
3. Append to `decisions.log.jsonl`:
   - `[<date>] [SKIP GATE] <gate> — reason: <reason> — user-approved`
4. Proceed flow as if the gate passed (mark in TASK GRAPH: `QA_OK (SKIPPED — see decision.log)`.

Syntax examples:
```
/che-skip qa T3 reason:"hotfix for staging - unit tests broken by unrelated infra"
/che-skip compliance-light ALL reason:"manually reviewing a huge PR; will redo compliance at the end"
```

---

## `/che-decisions`

**What it does:** Reads and prints (summarised) all entries from `decisions.log.jsonl` for the current session.
**When to invoke:** User wants to review trade-offs made so far.

---

## `/che-summary`

**What it does:** Generates an immediate interim summary (even if not all tasks are done) using the final_summary structure.
**When to invoke:** User wants a status dump before the che finishes naturally.

---

## `/che-abort`

**What it does:** Marks session as ABORTED. Writes a final aborted status to session.md and task_graph.md. Does NOT delete any files. Changes to code so far remain in worktree.
**When to invoke:** User wants to abandon this session before completion.
Agent action: ask confirmation first.

---

## `/che-parallel <optional worktree> [--max-parallel=3] [--serial]`

**What it does:** Explicit trigger for the parallel execution mode of the che. Different from `/che-act`: `/che-act` auto-picks serial vs parallel based on preconditions and asks you to confirm; `/che-parallel` explicitly ENABLES parallel mode and errors out early (instead of falling back) if parallel preconditions can't be satisfied.
**When to invoke:** You KNOW your tasks in task_graph.md are parallel-safe (independent files) and you want to force fan-out of 2-4 Devs at once instead of sequential. Or if auto-detection in /che-act passed but you want to override `max_parallel` cap.
**Agent action:**
1. Invoke `che-act` with flag `force_parallel=true`.
2. If any task envelope's `Blast Radius` still has globs → ERROR + demand user enumerates files (NO serial fallback). Parallel-or-bust when command is explicitly `/che-parallel`.
3. Otherwise: user confirm → call `che-executor-dispatcher`.
4. Same outputs as che-act (execution_batches.md, merge_audit, batch_execution_report, manual_test_plan, final_summary).
**Flags:**
- `--serial`: Forces sequential, one task at a time. Use when parallel causes issues and you want debug single-task mode.
- `--max-parallel=N`: Overrides concurrency cap. Max allowed value 4; if user passes >4, clamp to 4 + warning.
- `--purge-stale-locks`: Auto-purges `$CHE_SESSION_DIR/_locks/*.lock.json` from aborted runs — resolve path via `che_compute_paths` (asks confirm unless this flag present; NEVER inside worktree).
**Syntax examples:**
```
/che-parallel --max-parallel=4
/che-parallel /abs/path/to/worktree
/che-parallel --serial     # force sequential for debugging
```

---

## `/che-ship`

**What it does:** End-of-development ship: atomic conventional commits, push (creates remote branch if missing), opens a DRAFT PR against the default branch with a **readable PR body for low-context reviewers** (5 canonical sections, acronyms expanded first use, every change includes user impact, risks explain consequences, default English), assigns the PR to you (the user).
**When to invoke:** You finish a feature/bugfix, you're confident the worktree is correct, and you want commit + push + open PR. Can run AFTER the che loop ends, or standalone for any worktree.
**Agent action:**
1. Invoke `che-ship` skill.
2. Preflight: worktree confirmed; `gh auth status` OK; no secret files staged.
3. Propose a numbered atomic commit plan grouping the diff into conventional commits.
4. Wait for your explicit APPROVAL of the commit plan.
5. Apply each commit individually.
6. `git push --no-verify --set-upstream origin <branch>` (creates remote if missing).
7. Build readable PR body (default English; Portuguese only if YOU explicitly request) from: `$CHE_WORKSPACE_SHARED/manual_test_plan.md` + `PR_DESCRIPTION_TEMPLATE.md` (filled style reference, follow it strictly) + relevant decisions from `$(che_decisions_path)`. Resolve paths via `che_compute_paths`; NEVER read from inside the Che checkout folder (e.g. `<WORKTREE_ROOT>/.che-ai/*` or legacy `<WORKTREE_ROOT>/.trae/*`). Anti-pattern: never nest the Che source checkout inside a user project repo. Enforce §A-4.2 process gates (acronyms expanded, 1 bullet = 1 change + why, risk→consequence, plain steps to verify, ≤50 lines total).
8. Open DRAFT PR against default branch → assign to `@me` → print PR URL.
**Syntax examples:**
```
/che-ship
/che-ship --ticket PROJ-123 --slug feat-stripe-connect
/che-ship --draft-pr-title "feat(payments): Stripe Connect onboarding"
```

---

## `/che-fix <optional worktree>`

**What it does:** Bug fix che (DIFFERENT from feature che). Scientific debug loop: user provides expected behaviour + reproduction steps. Debugger expert builds hypotheses, instruments, reproduces, analyses, applies minimal fix + regression test, demonstrates it to you with clear steps to verify or shows the failing→passing test run.
**When to invoke:** You want to report an existing bug / wrong runtime behaviour and have it fixed. NOT for feature work.
**Agent action:**
1. Invoke `che-debugger-bugfix` skill.
2. Preflight: worktree path confirmed (ASK if missing).
3. Capture REQUIRED inputs from you: (a) expected behaviour, (b) actual bug behaviour, (c) exact numbered reproduction steps, (d) ticket reference if any.
4. Baseline: REPRODUCE the bug fresh → capture evidence (logs, stacks, HTTP).
5. Debug loop (max 5 iterations per bug): HYPOTHESIZE → INSTRUMENT → REPRODUCE → CONFIRM/REFUTE root cause.
6. Once root cause confirmed: write failing test → apply minimal fix → confirm test passes.
7. Deliver to you: (i) demo how to manually verify by running reproduction steps (before bad → after good), (ii) which files changed, (iii) where regression test file lives.
8. If stuck 5 iterations: stop, report what hypotheses were REFUTED, ask next steps.
**Syntax examples:**
```
/che-fix "HTTP 500 when submit order without customer_id"
/che-fix expected:"Dashboard shows £0.00 always even with sales" actual:"shows 0" repro:"1. login ...
```

---

## `/che-review <PR_URL> --ticket <LINEAR_OR_JIRA_URL or --scope "text description">`

**What it does:** High-impact focused code review of a GitHub PR. Only flags BLOCKING issues — never bikeshed style/formatting. Focus areas: (1) runtime breakage / silent incorrect behaviour, (2) security / PII / compliance, (3) unjustified new dependencies / huge PR scope, (4) scope deviation from ticket/description.
**When to invoke:** You paste a link of a PR you want a fast, meaningful review for.
**Agent action:**
1. Invoke `che-code-review` skill.
2. Preflight: `gh auth status` OK. Confirm PR URL is reachable and parseable.
3. Pull PR metadata + diff + files list via `gh pr view --json`.
4. Pull ticket context / scope description from your args.
5. Run the 4-category review framework (Runtime / Security / Deps-blast-radius / Scope deviation).
6. Structured review report saved to disk: resolve canonical OUTSIDE-WORKTREE path via `che_output_path "review" "che-code-review" "pr-<N>" "session" "md"` (NOT inside the Che checkout; NEVER hardcode `.trae/` or `.che-ai/` relative to worktree).
7. Verdict delivered to chat (Portuguese): 🔴 REQUEST CHANGES / 🟡 APPROVE WITH COMMENTS / 🟢 APPROVE, with numbered blocking issues.
8. If user says "suba essa review oficial": use `gh pr review` with the report as body + request-changes / comment / approve flag.
**Syntax examples:**
```
/che-review https://github.com/myorg/myrepo/pull/42 --ticket https://linear.app/team/issue/PROJ-123
/che-review https://github.com/myorg/myrepo/pull/42 --scope "fix checkout 500 when empty cart"
```

---

## `/che-diff <PR_URL OR --worktree /abs/path> [--base origin/dev]`

**What it does:** Lightweight "prepared conversation" about a diff. **DIFFERENT from `/che-review`** (which gives approve/request-changes verdict with CRITICAL + HIGH issues only). This delivers a 5-section report for YOU TO HAVE CONTEXT to discuss the diff with someone: (1) what it implements (high level), (2) main changes by module, (3) CI checks status (Mode A) or AlreadyCommitted/ToCommit/Untracked buckets (Mode B), (4) slight risks, (5) 3 attention points to discuss in a call/comment. Mode A = PR URL via gh CLI. Mode B = local worktree, compares with default branch (asks which base if ambiguous).

**When to invoke:** You pasted a PR link OR pointed to a worktree and want to "understand what happened here" + conversation points, without formal review rigor. When you want review blocking issues → use `/che-review`.

**Agent action:**
1. Invoke `che-diff-context` skill.
2. Preflight Mode A (PR URL): `gh auth status` OK; URL parseable and reachable.
3. Preflight Mode B (--worktree): worktree confirmed, §19 session binding read (ask mismatch). Base branch: auto-detect attempt (origin/main or origin/dev), if ambiguous → AskUserQuestion 2 options + "other".
4. Collect 3 context sources Mode A: PR descr/metadata via gh pr view --json, diff names/stat, CI checks gh pr checks.
5. Collect 4 buckets Mode B: Already Committed (base..HEAD), To Commit (staged + unstaged tracked), Untracked, Branch metadata.
6. Structure report in 5 CANONICAL sections (high context / change areas / CI or buckets / slight risks / 3 conversation points).
7. Save file via canonical helper: `che_output_path "diff_context" "diff-summary" "<pr-or-local>" "session" "md"` → resolves OUTSIDE the worktree to `$CHE_SESSION_DIR/diff_contexts/...`; NEVER hardcode `.trae/` or `.che-ai/` relative to worktree.
8. Deliver condensed summary in chat §18 contracts (250–500w + 4 sections). Full report saved to disk.

**Syntax examples:**
```
/che-diff https://github.com/myorg/myrepo/pull/42
/che-diff --worktree /abs/path/to/worktree
/che-diff --worktree /abs/path --base origin/dev
```

---

## `/che-manual-test <--worktree /abs/path> [--task-id <slug> OR --plan-path <abs/path/to/manual_test_plan.md>]`

**What it does:** Executes step-by-step the Scrum Master's `manual_test_plan.md` via **Playwright MCP** (real browser: navigate/click/fill/submit + screenshot evidence) and HTTP driver for API calls. DIFFERENT from `/che-qa` (QA = only automated build/lint/test commands without browser). This che Opens browser, step-by-step with plan, records evidence (PNG, visible_text, console_log) per step, and delivers final 8-section report with global verdict. Safety: DOES NOT touch prod URLs without 2 confirmations, mandatory setup approval gate BEFORE any shell setup command.

**When to invoke:** Scrum Master has finished the `manual_test_plan.md` (all plan ACs written, environment ready) and you want the AGENT TO EXECUTE the manual tests (open browser, click, fill forms, take prints) instead of you manually. If you only want automated build/lint/test → use `/che-qa`.

**Agent action:**
1. Invoke `che-manual-test-executor` skill IMMEDIATELY.
2. Preflight #1: confirm worktree path + validate §19 session binding (mismatch = block question).
3. Preflight #2: resolve manual_test_plan.md path → (a) `--plan-path` given → use; (b) default (no flag): `source "${CHE_HOME:-${HOME}/.che-ai}/contracts/che_sessions_contract.sh" && che_compute_paths $WORKTREE_ROOT && echo $CHE_WORKSPACE_SHARED/manual_test_plan.md`; (c) no binding created → AskUserQuestion which option.
4. Preflight #3: plan parse (§0 Setup env, AC-N steps with GWT, Smoke S1..S5, HUMAN_ONLY items §3).
5. **MANDATORY setup approval GATE (before any shell setup command):** ask user (A=Execute setup, B=Skip app already running, C=Cancel).
6. Create evidence dir: `$CHE_SESSION_DIR/manual_test_evidence/` (OUTSIDE worktree) with subdirs AC-1, AC-2, ... + `execution.log`.
7. **AC Execution Loop:** For each AC-N → step pattern classification → Playwright/HTTP driver. Step by step with evidence each. THEN final assertion → verdict ✅/⚠️/❌/⏭️ → close playwright session isolation.
8. **Smoke S1..S5:** S1=build, S2=lint via commands; S3=Login scenario Playwright; S4=top-level 3 pages Nav; S5=log grep CRITICAL/ERROR.
9. Build final 8-section report according to references/MANUAL_TEST_EXECUTION_REPORT.md → save to `$CHE_SESSION_DIR/reports/MANUAL_TEST_EXECUTION_REPORT.md` (OUTSIDE worktree, `che_assert_outside_worktree`).
10. Deliver condensed summary in chat §18 contracts (≤500w, 4 sections: status + ACs pass/fail counts + key failures ≤3 bullets + report/evidence/plan links + 1 deep-dive offer).

**Syntax examples:**
```
/che-manual-test --worktree /abs/path/to/worktree --task-id feat-PROJ-123-Process-a-refund
/che-manual-test --worktree /abs/path --plan-path /abs/che-ws-shared/some-other/manual_test_plan.md
```

---

## `/che-pr-comments <PR_URL>`

**What it does:** Scans every comment on a PR, classifies each one (human vs bot; valid actionable vs question vs nit vs outdated vs praise vs discussion). Produces a triage report with 3 outputs: (1) numbered implementation plan for comments we should act on, (2) pre-written ENGLISH polite responses for comments we decline/question, (3) comments we resolve silently. User approves the report → we implement + optionally post replies via gh.
**When to invoke:** PR has many review comments pending and you want a structured plan of what to fix vs how to reply.
**Agent action:**
1. Invoke `che-pr-comments` skill.
2. Pull ALL comments via `gh pr view --json comments,reviews` → flatten.
3. Classification framework: BOT vs HUMAN, then HUMAN → (CORRECTNESS, SECURITY, ARCHITECTURE, SCOPE CREEP, QUESTION, NIT, PRAISE, DISCUSSION, OUTDATED, DUPLICATE).
4. Triage report saved to `$CHE_WORKSPACE_SHARED/pr_comments/pr-<N>_<YYYYMMDD>.md` (resolve via `che_compute_paths`; NEVER inside the Che checkout folder nested in a user project, e.g. `<WORKTREE_ROOT>/.che-ai/` or legacy `<WORKTREE_ROOT>/.trae/`).
5. Deliver to user chat: summary buckets count, Section 1 (TO IMPLEMENT) sorted by severity, Section 2 (DRAFT RESPONSES) English polite non-argumentative, Section 3 DISCUSSION PENDING USER, Section 4 NIT optional, Section 5 RESOLVED SILENTLY.
6. Aggregated implementation plan as atomic commits batches.
7. If user says: implement → apply fixes in worktree. If user says: post replies → `gh pr reply` each drafted comment.
**Syntax examples:**
```
/che-pr-comments https://github.com/myorg/myrepo/pull/42
```

---

## `/che-ci-fix <ACTIONS_RUN_URL_or_PR_URL>`

**What it does:** Diagnoses and fixes failing CI (GitHub Actions). Pulls failed jobs/steps, extracts error logs, classifies root cause (build / lint / typecheck / deterministic-test / flaky / dependency-lockfile / CI-YAML-script / migration / INFRA-EXTERNAL — do not code). Proposes minimal fix plan per job. User approves plan → implements fixes in worktree locally → pushes. For INFRA/EXTERNAL (secrets rotated, GitHub outage, npm registry 5xx): stops and reports to user without touching code.
**When to invoke:** CI goes red on a PR or Actions run and you want a diagnosis + fix.
**Agent action:**
1. Invoke `che-ci-fixer` skill.
2. Preflight: `gh auth status` OK; worktree path confirmed (ASK if missing).
3. Pull failing jobs / steps via `gh run view` / `gh pr checks`.
4. For each failed step: pull logs → classify into R1-R9 categories (R9: intentional AC/spec changed → fix tests, not code; user confirm required).
5. Fix plan per job, grouped by category. Present to user for APPROVAL before coding.
6. For R7 (infra/external): IMMEDIATELY report to user — NO code changes.
7. User-approved plan → implement minimal fixes in worktree. Verify local equivalents.
8. Ship via same conventional-commit rules: `fix(ci):`, `fix(lint):`, `fix(build):`, `chore(deps):`, `chore(ci):`.
9. Push branch → optionally rerun failed jobs.
**Syntax examples:**
```
/che-ci-fix https://github.com/myorg/myrepo/actions/runs/987654
/che-ci-fix https://github.com/myorg/myrepo/pull/42
```

---

## `/che-design` <modo: A|B|C optional> [--path /abs/path/to/save.pen] [--palette #HEX1,#HEX2] [--tone "Tone of Voice"]

## Alias: `/che-figma`

**What it does:** Full design che: 3 modes. (A) Social Media: 6 creatives (Feed/Stories/Reels) + professional copy + IA generated images + 2× PNG export. (B) UI/UX Feature: wireframes → high-fidelity → dev-spec (exportable Tailwind tokens). (C) Atomic Design System: Tailwind tokens ↔ variables (Light/Dark mode) + 12 components (Button/Card/Input etc.) 4 variants + CSS/JSON/Tailwind export. Uses **local** `mcp_open-pencil` MCP (140+ tools equivalent to Figma desktop).
**When to invoke:** You want professional production-ready designs right from here: social media creatives with copy, product screens, or an atomic design system synced with Tailwind.
**Agent action (MANDATORY PREFLIGHT if parameters are missing):**
1. Invoke **`che-social-ui-designer`** skill IMMEDIATELY.
2. Preflight question #1 (if `--mode` omitted): "Which mode? A) Social Media / B) UI-UX / C) Design System" (AskUserQuestion 1 question, 3 options).
3. Preflight question #2 (equivalent to "which figma project to work on", user-asked): which ABSOLUTE path to save the design file (`.pen` = OpenPencil / Figma-equivalent). Default is the Che-scoped durable designs folder inside the BOUND worktree's shared workspace: `${CHE_WORKSPACE_SHARED}/designs/<mode>-<slug>-YYYYMMDD.pen`. If the session is not yet bound, use the user Che home designs subfolder: `"${CHE_HOME:-${HOME}/.che-ai}/designs/<mode>-<slug>-YYYYMMDD.pen"`.
4. Preflight question #3 (if missing): palette / typography / tone of voice (copy).
5. Skill executes selected mode §A/B/C with fail-fast + WCAG AA quality gates.
6. Final delivery always with: 2× PNG exported files / tokens / source `.pen` + ONE SINGLE offer to deep-dive (§18 contracts).

**Syntax examples:**
```
/che-design A                                # Full Social Media batch (2 feed + 2 stories + 2 reels templates + copy + images)
/che-design B --path /home/laion/designs/dashboard-creator.pen  # UI-UX dashboard feature
/che-design C --palette "#6D28D9,#F59E0B,#111827,#F9FAFB" --tone "Minimalist luxury"
/che-figma A slug:"UK-festival-launch"   # same alias
```

---

## Relationship between commands and skills (UPDATED)

| Command | Primary skill invoked |
|---|---|
| `/che-spec` | `che-spec` (4 input sources: existing / ticket URL / legacy PRD path / brief description; YAML frontmatter + 7 canonical sections; Approved gate; saves DURABLE workspace-shared; standalone or automatically invoked by SM §0.5 in /che-act) |
| `/che-act` | `che-act` (§0.5 auto-invokes che-spec if no Approved SPEC; auto-detects serial vs parallel; falls back to serial if any precondition fails) |
| `/che-parallel` | `che-act` → `che-executor-dispatcher` (explicit parallel; ERROR if cannot parallelise; no serial fallback) |
| `/che-ship` | `che-ship` (commits → push → DRAFT PR → assign) |
| `/che-fix` | `che-debugger-bugfix` (scientific debug loop, different from features) |
| `/che-review` | `che-code-review` (HIGH / CRITICAL + scope only) |
| `/che-diff` | `che-diff-context` (lightweight conversation context — NO verdict) |
| `/che-manual-test` | `che-manual-test-executor` (Playwright MCP + HTTP driver, manual_test_plan.md steps with screenshot evidence + 8-section report. MANDATORY setup approval gate. Boundary vs che-qa: QA = automated build/lint/test; Manual = real browser/interactive.) |
| `/che-pr-comments` | `che-pr-comments` (triage, implementation plan, reply drafts) |
| `/che-ci-fix` | `che-ci-fixer` (classify CI failure + minimal fix) |
| `/che-design` | `che-social-ui-designer` (3 modes: Social Media / UI-UX / Design System — local open-pencil Figma-equivalent MCP) |
| `/che-status` | Reads `task_graph.md` directly, no skill invocation needed |
| `/che-skip` | Updates `decisions.log.jsonl` + `task_graph.md`; tells SM to treat gate as passed |
| `/che-decisions` | Reads `decisions.log.jsonl` |
| `/che-summary` | Uses SM logic to generate interim final_summary |
| `/che-abort` | SM writes ABORTED metadata |
| `/che-config` | `che_core.cli config` |
| `/che-export` | `portability.py` logic | Exports project durable data (L2+L3) to a portable archive. |
| `/che-import` | `portability.py` logic | Imports project durable data from archive. |

---

## `/che-config [--lang-chat=...] [--lang-docs=...] [--lang-report=...] [--pt-check=...]`
**What it does:** Sets configuration flags for the current session, such as chat language, documentation language, and Portuguese text detection. Flags are stored in the Level 1 registry.
**When to invoke:** When you want to change the agent's behavior regarding language or security hooks for the current session.
**Agent action:**
1. Resolve `WORKTREE_ROOT` and `SESSION_ID`.
2. Execute: `python3 -m che_core.cli config "$SESSION_ID" "$WORKTREE_ROOT" ...`.
3. Report the updated configuration to the user.

---

## `/che-export <worktree> [output_file]`
**What it does:** Exports the perennial knowledge of the current project (L2 Project Metadata + L3 Worktree Shared Strategy) to a portable `.tar.gz` archive. Excludes ephemeral session data (L4).
**When to invoke:** When you want to port a project's architecture, specs, and business context to another machine or backup.
**Agent action:**
1. Resolve `WORKTREE_ROOT`.
2. Determine `output` path (default: `$HOME/che-export-<project-slug>.tar.gz`).
3. Execute: `python3 -m che_core.cli export "$WORKTREE_ROOT" "$OUTPUT_PATH"`.
4. Report success and file location to the user.

---

## `/che-import <archive_path> [--workspace name]`
**What it does:** Imports a previously exported Che project archive. Recreates the L2 and L3 structures on the new machine.
**When to invoke:** When you receive a Che archive and want to set it up in your local environment.
**Agent action:**
1. Execute: `python3 -m che_core.cli import "$PATH" ${WORKSPACE:+--workspace "$WORKSPACE"}`.
2. Resolve naming conflicts by appending `--import-YYYYMMDD-HHMM` to slugs if they already exist.
3. Parse JSON response and report the new slugs and directories to the user.

---

## Rules for the AGENT when user issues a command

1. **Worktree check FIRST.** If `/che-*` is called but worktree is not yet confirmed → **ASK FOR WORKTREE before executing anything else.** Even if the command is just `/che-status`. EXCEPTION: `/che-spec` runs preflight binding if none exists (auto-creates Level 1+2).
2. **English for files, Portuguese for chat.** The reports printed to the user (status, decisions, warnings) are in Portuguese (as per user preference). The files written to disk are in English.
3. **Do NOT invent new commands.** Only those listed above, plus any repo-local commands already defined per-worktree.
4. **Logging.** Every command execution results in a new entry to `session.md` under `$CHE_SESSION_DIR/` (resolved via `che_compute_paths` contract; NEVER inside the Che checkout nested inside a user worktree, e.g. `worktree/.che-ai/` or legacy `worktree/.trae/` — §19.1 MORATORIUM).
5. **SPEC GATE precedence order for planning:**
   - Standalone `/che-spec` = document only (no scope-capture / dev), runs before che-act.
   - `/che-act` = SM §0.5 auto-calls che-spec IF no Approved SPEC exists, passing user input args (ticket/prd/desc); Approved releases scope-capture.
