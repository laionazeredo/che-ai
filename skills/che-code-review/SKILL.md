---
name: "che-code-review"
description: "High-impact code review with TWO MODES: (A) GitHub PR URL as before, or (B) LOCAL WORKTREE MODE when user passes --worktree <path> WITHOUT a GitHub PR URL — reviews files currently in the modification/staging area (git status + git diff). Resolves project rules deterministically via `che review rules` (layered precedence, path scoping, explicit conflict reporting) before reviewing. Focuses ONLY on blocking issues: runtime regressions, security/PII leaks, unjustified dependencies, and scope deviations. Invoke when /che-review is called or user asks for code review."
---

# Che — Code Review (High Impact Focused)

> **SHARED REFERENCES (CANONICAL — DO NOT DUPLICATE body here):**
> - Security + PII + RLS review checklist: `_shared_checklists/SECURITY_PII_COMMON.md`
> - GitHub CLI gh auth + PR operations: `_shared_checklists/GITHUB_CLI_COMMON.md`

Reviewer role with **two mutually exclusive modes** (choose EXACTLY one):
- **Mode A (Classic)**: Already-opened GitHub Pull Request review via `gh` CLI from PR URL.
- **Mode B (NEW — Local Worktree)**: Local code review of modified/staged files inside a worktree (when user passes `--worktree <path>` or explicitly says "review this worktree" and NO GitHub PR URL was provided).

**Deliberately narrow scope so it's useful without being pedantic.**
We NEVER pick on style, format, naming, Biome warnings (those are CI/lint jobs).
We ONLY flag things that actually break production or waste $$$ or risk users.

---

## 0. Preconditions — Two modes (PICK EXACTLY ONE)

### 0.1 WORKTREE SESSION BINDING CHECK (engineering-contracts §19, NON-NEGOTIABLE, common to BOTH modes)

Run THIS BEFORE deciding mode or starting any review context gathering.

1. **Read Level 1 Global Index FIRST:** Read `$CHE_REGISTRY_PATH`. Find LAST STATUS=BOUND entry using the effective session id from `${CHE_SESSION_ID:-${HARNESS_SESSION_ID:-$SESSION_ID}}`. Use its WORKTREE_ROOT for the session.
2. **Mode B mismatch check (CRITICAL):**
   - If user passed --worktree <path>: confirm Level 1 registry WORKTREE_ROOT EXISTS and is DIFFERENT than <path> → BLOCK.
   - Ask: "You asked review on worktree X but Level 1 GLOBAL session is BOUND to Y. Options: (A = X, override binding; B = Switch binding first (§19.3 re-bind chain); C = Cancel review). NEVER silent override. If no Level 1 entry → binding not made; proceed to decision flow to create binding (§19.2) only if user continues."
3. **Mode A PR URL + local worktree:** PR for branch that resides Level 1 registry says BOUND on some worktree:
   - If PR is for branch worktree B and user says --worktree pointing to A → BLOCK. Ask which is correct.
4. **Pre-send ref trimmer (global):** Output final report refs file links MUST NOT span ≥2 worktrees unless user explicitly asked cross-worktree comparison. Trim to single scope before sending.

---

### How to decide which mode
- If user provides **BOTH a GitHub PR URL AND --worktree** → prefer Mode A (PR URL); --worktree becomes optional local path for writing report to disk only.
- If user provides **--worktree <path> (or equivalent explicit worktree indicator) AND NO GitHub PR URL** → **FORCE Mode B (Local Worktree)**. Do NOT ask for a PR URL.

---

### Mode A — GitHub PR URL mode (unchanged classic path)

1. **PR URL** (GitHub). Example: `https://github.com/owner/repo/pull/123`
   - **IMPORTANT**: User rules: when working with GitHub → use `gh` CLI (not browser).
   - Pre-flight: `gh auth status` — if not logged in → guide user to `gh auth login` then stop.
2. **Ticket link OR scope description**:
   - Linear/Jira URL + what the PR is SUPPOSED to do
   - OR plain text description of scope/goals
   - If missing → ASK user for it. Cannot review scope adherence without knowing intended scope.
3. (Optional) Worktree path if user wants local review & fixes right away — otherwise, just review, no local edits.

---

### Mode B — NEW: Local Worktree Modification Area mode (NO GitHub PR URL)

Trigger condition: user passed `--worktree <path>` OR explicitly pointed to a worktree AND did NOT provide any GitHub PR URL.

Preconditions (MANDATORY checks BEFORE starting review):
1. **WORKTREE_ROOT** = absolute path provided by user (e.g. from `--worktree` flag or explicit path).
   - Validate: `cd <WORKTREE_ROOT> && git rev-parse --is-inside-work-tree 2>/dev/null` returns `true`. If not → stop with error "Not a valid git worktree: <path>".
2. **Ticket link OR scope description**:
   - Same requirement as Mode A (Linear/Jira URL or plain text scope/goals).
   - If missing → ASK user for it. Cannot review scope adherence without knowing intended scope.
3. **Modification area non-empty check** (optional warning):
   - Run `cd <WORKTREE_ROOT> && git status --short`
   - If output is EMPTY (zero files modified/staged/deleted/untracked):
     → WARN user "Worktree modification area is empty — there are no changed files to review. Proceed anyway to review full repo against scope? [Y/n]". Wait confirmation. If user says no → stop; if yes → review all touched files from last commit or proceed with user's clarification.

---

## 1. Gather context — Mode-dependent path

### Mode A (GitHub PR) → use gh CLI (no browser)

#### 0.5 MANDATORY GH PREFLIGHT (engineering-contracts §18 gh-cli-only rule + load PR comments INTO CONTEXT)

Before ANY other operation in Mode A (PR URL), run this block to: (a) ensure gh CLI available and logged in, (b) LOAD INTO REVIEW CONTEXT **ALL PR comments (inline review comments + general PR body discussion comments + review-level comments)** as they heavily influence our analysis: if a colleague has already raised a point, we do not want to report the same thing duplicated (or if we do, cross-link explicitly and explain if we agree/disagree).

```bash
# (a) gh Preflight
command -v gh >/dev/null 2>&1 || { echo "❌ gh CLI not installed. Install via https://cli.github.com/ + gh auth login --scopes repo,read:org,workflow"; exit 6; }
gh auth status >/dev/null 2>&1 || { echo "❌ gh CLI not authenticated. Run: gh auth login --scopes repo,read:org,workflow"; exit 7; }

# (b) LOAD COMMENTS from 3 distinct sources:
#     Source 1 = comments[]           → PR-LEVEL discussion comments (Conversation tab, generic, not tied to code)
#     Source 2 = reviewComments[]     → INLINE review comments (tied to specific code hunks, with reply threads)
#     Source 3 = reviews[]            → Complete REVIEWS (APPROVED / CHANGES_REQUESTED / COMMENTED) + review body + state
gh pr view <PR_URL> --json comments,reviewComments,reviews > /tmp/pr-<PR_ID>-all-comments.json
```

**Mandatory rule regarding loaded comments (DO NOT SKIP):**

1. **Ingestion and flatten:** Normalize the 3 arrays into a single `PR_COMMENTS[]` list where each item has: `{source: "pr-comment" | "inline-review" | "review", id, path|null, line|null, author, state|null, createdAt, body, replyToId|null, resolvedStatus|null, isDraft, url}`. Sort by `createdAt` ASC to understand discussion timeline.
2. **DO NOT duplicate findings.** Before classifying a new finding (Category 0/1/2/3/4/5), compare against `PR_COMMENTS[]`:
   - **Strong match:** If there is an inline comment (same `path` + `line` ±10 lines in same diff hunk) with same theme (e.g. both speak of "missing null guard on `x.user`"), then:
     - If the human comment is more complete and we have nothing more to add: **OMIT the finding, DO NOT emit duplicate**; instead, add a special section to report: **`🎯 Existing Human Review Threads (Not Repeated)`** listing (id, path, author, 1-line point summary, resolved status? resolved by whom?).
     - If we have additional info / disagree / have a reproducible example the human did not include: **EMIT the finding normally but start with a MANDATORY prefix:**
       > `[Cross-ref PR inline comment #<id> by @<author> — extends / partially agrees / respectfully disagrees because <1 line rationale>]`
       and at the end of the finding add `→ Thread: <url>` pointing to the original comment.
   - **Weak match:** conversation-level generic comment ("this PR needs better error handling", no specific path/line): not a duplication, process normally but if our finding covers exactly that point → list the pairs in `Existing Discussions Addressed In This Review` at the end of the report.
3. **Review state aware.** If `reviews[]` has a recent `CHANGES_REQUESTED` from an OWNER/CODEOWNER, DO NOT recommend `APPROVE` at the end unless user explicitly asks for override + we have 0C/0H + all CR points addressed. Always include a line in executive summary: **`Current PR review state: <N> APPROVED, <M> CHANGES_REQUESTED (authors: @a, @b), <K> COMMENTED`**.
4. **Resolved threads do not count for findings to be repeated**, but count as discussion history useful for understanding author trade-offs → read the body.
5. **Draft comments (`isDraft: true`)** are private to the author and must be ignored.

**Expected result of Step 0.5:** You have `ALL_COMMENTS[]` and `REVIEW_STATE_STATS` in memory, and ALWAYS include the two additional sections below in report output (between `Executive Summary` and `Category 0`):
- `🎯 Existing Review Context (from PR comments)` — basic stats + important unresolved threads
- `🤝 Findings Alignment with Human Comments` — one line per ≥MEDIUM finding indicating if: (new / omitted duplicate / extends human / disagrees with human)

#### 1.1 PR metadata + diffs

> Note: `comments,reviews,reviewComments` already fetched in step 0.5 above. Below we fetch only remaining fields (files, commits, etc.) and unified diff.

```bash
gh pr view <PR_URL> --json \
  number,title,body,author,state,isDraft,baseRefName,headRefName,additions,deletions,changedFiles,commits,labels,reviewDecision,mergeable,files,author,assignees,maintainerCanModify
```

Record:
- `PR_ID` = number (e.g. 123)
- `BASE_BRANCH`
- `HEAD_BRANCH`
- `changedFiles_count`
- `diff_stat` (additions / deletions)
- Author, labels
- files[] (list of changed files + patches)

#### 1.2 Ticket context

Parse the ticket (Linear/Jira) if provided — via appropriate API (user rules: Linear via GraphQL API, Jira via env vars API). Extract:
- Task **Goal** / acceptance criteria list
- **Out-of-scope** / explicit non-goals
- Expected files / risk areas

If no ticket given, the user's plain text description becomes the reference scope.

---

### Mode B (Local Worktree) → use git commands directly (NO gh / NO network)

Run ALL of these inside `<WORKTREE_ROOT>` directory. Never leave the worktree.

#### B-1.1 Capture modified/staged/untracked files + diffs

**Step 1: get full file list (union of staged + unstaged + untracked tracked files).**

```bash
# Summary list (short format — for display + counting):
git status --short

# Individual diffs needed for review (combine BOTH staged + unstaged changes):
#   B-1.1.1: staged diff (files already "git add"ed)
git diff --cached --unified=3

#   B-1.1.2: unstaged diff (working tree modifications not yet added)
git diff --unified=3
```

**Step 2: build canonical file list `changedFiles[]` we review.**
Rules:
1. Parse `git status --short` output (short format flags: `M` = modified, `A` = added, `D` = deleted, `R` = renamed, `??` = untracked).
2. **Include in review list:**
   - Files with status: `M`, `A`, `R`, `C` (copied), `T` (type changed), `U` (unmerged) — both staged and unstaged variants: ` M` (unstaged only), `M ` (staged only), `MM` (both) → all included.
   - `??` (untracked files): **INCLUDE ONLY if they look like code/config (exts: .ts,.tsx,.js,.jsx,.py,.rs,.go,.java,.kt,.sql,.json,.yaml,.yml,.toml,.md where .md is a PRD/spec doc NOT generic README fluff; if user clarifies to include extra, honor that).**
   - Skip binary auto-generated build artifacts (node_modules/, dist/, .next/, build/, coverage/, *.png, *.jpg, *.pdf, *.lock diffs auto-generated by package managers — treat as out-of-scope unless scope says otherwise).
3. **For each file in canonical changedFiles[]:**
   - Record relative path, change type (M/A/D/R/??), count added/deleted lines from its diff block.
   - If file is untracked (`??`) AND new → its "patch" = FULL file content (treat as 100% additions diff block): read it whole via `cat`.
4. Aggregate:
   - `changedFiles_count` = N files in canonical list
   - `diff_stat` = total additions / total deletions (sum from B-1.1.1 + B-1.1.2, excluding skipped binaries/locks)
   - `BASE_BRANCH_HEURISTIC`: run `git rev-parse --abbrev-ref HEAD` → current branch name (for info only — no base/head concept locally; base is assumed what is committed on this branch before modifications)

#### B-1.2 Ticket context

Same as Mode A 1.2 — parse ticket (if provided) or use user's plain text scope description.
**CRITICAL for Mode B**: because there's no PR body describing intent locally, the ticket + user scope description becomes the ONLY authority for Category 4 (Scope Deviation) classification. Be conservative.

---

## 1.5 PROJECT RULE RESOLUTION — (MANDATORY NEVER-SKIP; runs for BOTH Mode A and Mode B)

> **GOAL:** before looking at ANY diff finding, know which project rules actually apply to THIS diff, and which of them outrank the others. Reading rule files ad hoc cannot do that: two contradictory rules read in file order produce a verdict that depends on the reading order, not on the project. The resolver ranks them once, deterministically, and reports what it could not rank.

**The resolver is the ONLY source of rule authority.** Never quote a project rule that did not come out of it. It remains your job to READ the files it points at — a citation is not context.

### 1.5.0 Resolve (one command, deterministic)

```bash
# Project memory is optional: without a bound project the resolver still returns repository rules.
eval "$(che compute_paths "$WORKTREE_ROOT" "$SESSION_ID" --cwd "$PWD")" 2>/dev/null || true

che review rules \
  --worktree "$WORKTREE_ROOT" \
  ${CHE_PROJECT_SLUG:+--project "$CHE_PROJECT_SLUG"} \
  --changed <file1> <file2> ... \
  --json > "$CHE_SESSION_DIR/review-rules.json"
```

- Pass `--changed` with the diff paths already known (Mode A: `gh pr diff <PR> --name-only`; Mode B: the B-1.1 list). Without it the resolver falls back to `git status`, which is not the PR diff.
- Read the JSON once and keep it in context. Keys: `params`, `hard_floor`, `rules`, `conflicts`, `drift`, `sources`, `ignored`, `budget`.
- If the command fails, report the failure and STOP. Do NOT fall back to reading `.claude/rules/*` by hand — that reintroduces the ordering bug this exists to remove.

### 1.5.1 Authority layers (fixed — never invent a new one)

| Layer | Source | Rank | Rule |
|---|---|---|---|
| `hard-floor` | Che invariants (security/PII, storage boundary, worktree binding) | 0 | Never loosened by any project rule. |
| `repo-explicit` | `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `.github/copilot-instructions.md`, `.claude|.agents|.cursor/rules/*`, package-level `AGENTS.md`/`CLAUDE.md` | 1 | The project's written law. |
| `machine` | eslint / biome / tsconfig / ruff / CI workflows | 2 | Already enforced by tooling — never re-flag as a review finding. |
| `project-memory` | `project_profile.md`, `architecture.md`, `product_context.md`, `<domain>/conventions.md` | 3 | Derived memory. Layer 1 always wins; a divergence is `drift`. |

Two authorities are NOT files, so the resolver cannot see them: the **Approved SPEC / ticket** (authority over scope, Category 4) and the **Che global defaults** (`engineering-contracts` §1-21 + Categories 0-8, the baseline). They sit above and below this table respectively and are never overridden by it.

### 1.5.2 Apply the resolved set (tighten-only)

1. **`hard_floor`** — always in force. A project rule may add to it, never relax it.
2. **`rules`** — the applicable set. Cite `source:line` verbatim in every finding it supports.
   - `superseded_by` is NOT null → **never cite that rule**; a higher layer already won.
   - `conflicted: true` → cap the finding at MEDIUM and cite BOTH sides (§1.6).
3. **`params`** — `min_severity` sets what may be reported, `blocking` decides the verdict, `ignore_paths` are excluded, `risk_paths` force the deep read in §1.5.4.
4. **`machine` sources** — listed for completeness only. If a tool already catches it, it is not a review finding.
5. **`ignored`** — read the reasons. A rule that is path-scoped out, below `min_severity`, or over budget must never be quoted later as if it applied.

### 1.5.3 Context reads (NOT rule authority — read for rationale)

For each file below in `<WORKTREE_ROOT>`, read it if it exists, as **context** for why the code looks the way it does. None of these can create a rule; only the resolver does that.

| # | File(s) (read if exists) | Why |
|---|---|---|
| R1 | `README.md` at repo root | Stack, commands, high-level architecture (one pass). |
| R2 | `docs/plan.md` | Fixed constraints (closed vs open scope). |
| R3 | `docs/decisions.md` or `docs/adr/*.md` (5 most recent) | Decisions with RATIONALE — why the layering is what it is. |
| R4 | `graphify-out/GRAPH_REPORT.md` | Community hubs and file paths for the diff area. |
| R5 | `<package>/README.md` and `docs/<area>.md` for every affected package | Package-level context (payment flow, scanner, db). |
| R6 | Local review skill: `.claude/skills/*/SKILL.md`, `.agents/skills/*/SKILL.md` matching review/audit | The project's own checklist. Absorb its checks into Categories 0-8 — the resolver does not parse skills. If it names specific files to read, READ THEM NOW. |

**All R1-R6:** `Glob` first, then `Read` each that exists. `AGENTS.md`/`CLAUDE.md` are deliberately NOT here — their rules arrive through the resolver (§1.5.0); reading them again adds prose, not authority.

### 1.5.4 Cross-file pipeline reads (driven by the diff, not by docs)

The resolver says which RULES apply; these say which CODE to compare against code. Mandatory whenever the diff touches the area:

1. **Webhooks** — diff touches `webhook`, `Webhook*`, `api/webhooks/*/route.ts`, `supportedTypes` → READ the ROUTE-level dispatcher and compare its allowlist with the service's supported types.
2. **PSP / Connect** — diff touches charges, refunds or transfers → READ every PSP call in the same package, not just the diff hunk.
3. **Affected packages** — for each package in the resolver's `sources`, read `<package>/AGENTS.md` and `<package>/CLAUDE.md` if they exist. Their rules already arrived resolved; this is for surrounding context.

### 1.5.5 Bootstrap confirmation checklist (DO NOT proceed without marking ALL)

Before entering §2 Review Framework — answer these SILENTLY. If ANY is NO, go back.

```
[ ] `che review rules` ran and its JSON is in context
[ ] params internalised (min_severity, blocking, ignore_paths, risk_paths)
[ ] hard_floor acknowledged as non-overridable
[ ] every conflict and drift entry read; §1.6 applied to each
[ ] ignored reasons read (no path-scoped / below-floor rule will be quoted later)
[ ] context reads R1-R6 done for every file that existed
[ ] diff touches webhooks? YES → route-level allowlist file ALREADY READ
[ ] diff touches PSP/Connect charges/refunds/transfers? YES → ALL psp calls in the package ALREADY READ
```

---

## 1.6 CONFLICT PROTOCOL (the resolver reports; you obey)

| Situation | What you do |
|---|---|
| `kind: precedence` | Cite ONLY `winner_source`. Never cite `loser_source` as authority. |
| `kind: precedence` + a `drift` entry | Same as above, and surface the drift ONCE in the report (`⚖️ Rule Resolution`) — not per finding. If the user asks, propose `che knowledge apply` to fix the stale memory. |
| `kind: unresolved` | Both rules stay in force for their own subjects. Any finding from that topic is capped at **MEDIUM**, never blocks, and cites BOTH sides. Ask the user ONLY if the cap changes the verdict (it would have been CRITICAL/HIGH). |
| Rule needed but absent from `rules` | Say so explicitly ("no project rule returned for X; judged on Che defaults") instead of inventing authority. |
| Project rule contradicts `hard_floor` | `hard_floor` wins. An override needs the user's verbatim justification logged via `che decision_append`, and is reported as an override — never silent. |
| No project files at all | Proceed on `hard_floor` + Che defaults and say so in `⚖️ Rule Resolution`. An empty rule set is a finding about the repository, not a licence to improvise. |

**Never** resolve a conflict yourself by preferring the rule you find more reasonable. That is exactly the non-determinism this protocol removes.

---

## 2. Review framework — 5 categories ONLY

We only look at these 5. Anything else is out-of-scope for this reviewer role.

> **Simplicity Bias lens (engineering-contracts §1 — the touchstone):** while applying the 5 categories, also weigh the solution against the bias. Flag **premature completeness** (edge-case/error/validation handling no current AC demands), **irreversibility** (hard to change or undo), and **blind spots** (no observability at a seam the diff touches) — MEDIUM by default, HIGH when they cause real fragility. A complete-but-fragile or complete-but-invisible solution is not better than a smaller reversible one.

---

### Category 0: 🔴 Cross-File Pipeline Integrity Checks (CRITICAL or HIGH; never skip)

These are "diff looks fine, but upstream entry point dropped it" bugs that unit/E2E tests miss because tests call services directly. Run EVERY subheading below — if diff touches ANY mentioned keywords, you MUST do the cross-file read.

#### 0.1 Webhook pipeline entrypoint allowlist vs service handlers (CRITICAL if mismatch)
If diff touches files with `webhook`, `Webhook*Service`, `supportedTypes`, `handleStripe*`, `charge.`, `customer.`, `route.ts` under `api/webhooks/`:

1. Read **ROUTE-level allowlist** (early arrays like `stripeSnapshotEventTypes`, `acceptedEvents` at TOP of `/api/webhooks/*/route.ts` or dispatcher functions).
2. Read **service handler's supported events** (e.g. `WebhookService.supportedTypes`, switch-cases inside `handleEvent`).
3. **CRITICAL if:**
   - Service handles an event type NOT in route-level allowlist.
   - Route returns `202 / ignored: true` / drops events service actually needs.
   - Note: tests calling `svc.handleEvent()` directly BYPASS this check — inspect real route file, not test.
4. Fix: add missing type to allowlist + require signed-payload route-level POST test.

#### 0.2 Connect / PSP charge-model consistency (CRITICAL if contradiction)
If diff touches `createPaymentIntent`, `createRefund`, `transfer`, `reverse_transfer`, `stripeAccount`, `transfer_data.destination`, `on_behalf_of`, `application_fee_amount` or equivalent PSP params:

> **MANDATORY 3-PASS PROCEDURE — DO NOT SKIP any:**
> 
> **Step 1 (extract createPaymentIntent params):**
> Find line where `paymentIntents.create(...)` / `createPaymentIntent(...)` called.
> - (a) 2nd arg (headers): exists `{ stripeAccount: X }`? Note `X` value (e.g. `payload.stripeConnectedAccountId` variable).
> - (b) 1st arg (body params): exists `transfer_data: { destination: Y }`? Note `Y` value.
> 
> **Step 2 (detect createPaymentIntent contradiction):**
> IF (a) AND (b) BOTH true → compare `X` and `Y`.
> - **CRITICAL if `X === Y`** (destination = same account emitting request). Reason: Stripe rejects with HTTP 400 `transfer_data[destination]` cannot equal account making request → ALL Connect checkout fails.
> 
> **Step 3 (cross-check createPaymentIntent model vs createRefund model):**
> After classifying createPaymentIntent as DESTINATION CHARGE (only (b), no (a)) or DIRECT CHARGE (only (a), no (b)), now find `createRefund(...)` or `refunds.create(...)`:
> - (r1) exists `stripeAccount` header?
> - (r2) exists `reverse_transfer: true`?
> - **CRITICAL if createPaymentIntent = DESTINATION CHARGE (platform creates) AND createRefund uses connected stripeAccount + reverse_transfer: true**. Reason: `reverse_transfer` only works in refunds issued FROM platform (stripeAccount not set). createRefund with connectedAccountId stripeAccount searches for charge/pi inside connected account — but destination-charge PIs live on PLATFORM account → wrong namespace. Stripe won't find it → 404.
> - **CRITICAL if createPaymentIntent = DIRECT CHARGE (stripeAccount=X) AND createRefund NO stripeAccount=X AND HAS reverse_transfer=true**. Reason: direct charge had no transfer_data to reverse; refund comes from connected account, but request without stripeAccount hits platform account → 404 charge not found.

1. Classify formally (after 3-pass above):
   - **Destination charge model:** PI created ON platform account (no `stripeAccount` on create); `transfer_data.destination=connected`, `application_fee_amount`, `on_behalf_of` present. Refunds from platform with `reverse_transfer: true`.
   - **Direct charge model:** PI created WITH `{ stripeAccount: connectedAccountId }` header; NO `transfer_data.destination` (PSP rejects if equal to requester); refund issued with same `stripeAccount` header.
2. **CRITICAL if (after 3-pass):** any method mixes models. Examples:
   - `createPaymentIntent` issued with `stripeAccount` (direct) but still carries `transfer_data.destination = same account` → request fails.
   - `createRefund` issued with `stripeAccount:` header AND `reverse_transfer: true` → reverse_transfer only for destination-charge model; wrong ID namespace if PI on platform account.
3. Fix: pick one model end-to-end; keep refunds/PIs consistent. Mock clients mask this — READ real client parameterisation.

#### 0.3 Transaction + row lock duration vs network calls (HIGH if overlap)
If diff contains BOTH (a) transaction/lock primitives AND (b) external network awaitables:
- (a) signals: `queryRunner.startTransaction()`, `manager.transaction()`, `setLock("pessimistic_write")`, `lockForUpdate`, `FOR UPDATE`, `BEGIN`;
- (b) signals: `await stripe.*`, `await fetch`, `await mailer.send`, `await new Promise(...setTimeout...)`, retry/backoff sleeps.

1. Trace span: `tx start → [await network call(s) with backoff?] → tx commit/rollback`.
2. **HIGH if:** any external network await with backoff falls inside span. Reason: pool ceilings (e.g. ≤10 PgBouncer sessions) → risks DB-connection-exhaustion 500s across app.
3. Fix: 2-phase — short tx #1 writes PROCESSING/idempotency claim + commits; network call outside tx; short tx #2 side effects / marks failed.

#### 0.4 Serverless fire-and-forget post-response work (HIGH if non-awaited)
If diff contains `void (async () => ...)();` or `setImmediate(async ...)` or `setTimeout(async ...)` wrapping:
- outbound emails (mailer.send / notification adapter),
- analytics/ETL upserts (sales_by_date, aggregator ON CONFLICT writes),
- event publishes / logger flushes.

1. Does HTTP/tRPC return BEFORE tasks are awaited?
2. **HIGH if yes.** Reason: Vercel/Next serverless may freeze at response; work silently lost. In-process E2E tests pass as they wait 30ms — doesn't reflect prod.
3. Fix: `waitUntil` (`@vercel/functions` / `Next after()`) or await before return; add route-level test.

---

### Category 1: 🔴 Runtime breakage / silent incorrect behaviour (CRITICAL if found)

What counts (Category 0 + 1 together = CRITICAL or HIGH runtime):
- **Possible NullPointer / undefined field dereference** (access `obj.field.subfield` where `obj.field` can be null/undefined based on types/schema and no guard).
- **Race conditions**: async ops with TOCTOU, unhandled Promise rejections, missing `await` on async functions, `Promise.all()` silent fail, shared mutable state race.
- **Wrong algorithm / calculation**: obvious logic errors (if/else swapped, `<=` vs `<`, `+` vs `-`, currency divided by 100 twice so $1.00 → $0.01).
- **Schema backwards-incompatible change**: API returns type old clients can't handle.
- **Wrong API usage**: calling deprecated endpoint/method upstream docs say will fail (e.g. Stripe v1 endpoint in v2-only integration).
- **Missing null/empty handling**: DB returns `[]` for "empty" vs `null` for "not queried" and code treats same.
- **Boundary conditions**: off-by-one, index `-1`, pagination truncation, decimal precision loss in currency (float `0.1 + 0.2` for money — MUST use integer cents or Decimal).
- **Unverified type cast**: `as T` in TS without runtime guard; data from API/DB/JSON assumed typed but never checked.
- **PSP charge/version assumptions**: handler reads nested fields (e.g. `charge.refunds.data[0]`) depending on version/expansion; no undefined-check → silent drop. (Also cross-check with 0.2.)
- **Timezone incorrectness**: stored-local times treated as UTC in comparisons (e.g. BST vs UTC makes "event started" gates ±1h wrong). MEDIUM if gated; HIGH if user-visible eligibility.
- **Row multiplication + LIMIT 1 queries**: LEFT JOIN 1:N relations (items/inventories/events/org accounts) + LIMIT 1 returns arbitrary row → wrong org/event/time. HIGH if money or security; else MEDIUM.
- **null-cast quirks in ORM find-options**: `null as unknown as undefined` where IsNull() needed. MEDIUM default; HIGH if field is part of idempotency/composite PK.
- **Crash-safety "PROCESSING first" writes in same transaction as external await (MEDIUM/HIGH — Category 0.3 linked)**. If DB tx writes PROCESSING row (claim/idempotency) and does `startTransaction()` → write PROCESSING → `await stripe_network_call` → `commit`. Any crash/rollback will DELETE PROCESSING row too (tx never committed). Result: "intermediate PROCESSING state never survives failure" and catch block `markFailed` becomes dead code. **MEDIUM if also Category 0.3 HIGH.** Fix: Category 0.3 2-phase pattern — Tx1 writes and COMMITS PROCESSING row BEFORE network call.
- **Error message substring match brittle vs error.code enum match (LOW/MEDIUM)**. Handler/caller checks `e.message.includes("already been used/scanned")` vs `(e as RefundValidationError).code === "TICKET_ALREADY_SCANNED"`. MEDIUM if from service boundary. LOW if only logging.
- **Circular imports via cross-import error classes/services (LOW/MEDIUM)**. Service A imports `SomeError` from Service B, Service B imports symbols from Service A → circular chain. MEDIUM if causes runtime undefined (TS strict mode warns). Fix: move shared errors/enums to dedicated `domain/errors.ts`.
- **Entity decorator index names vs migration index names DRIFT (LOW/MEDIUM)**. TypeORM entity `@Index("idx_refunds_stripe_refund_id", { unique: true })` vs migration `uq_refunds_stripe_refund_id` (different name), or entity @Index() unnamed vs named migration. Result: next `migration:generate` emits spurious DROP/CREATE churn. MEDIUM if >2 mismatches.
- **Idempotency find-options NULL match via `null as unknown as undefined` → HIGH if idempotency/composite PK (already listed)**.

Each entry: CRITICAL severity unless provably unreachable.

---

### Category 2: 🔴 Security / PII / Compliance (CRITICAL or HIGH)

Reuse **che-compliance** skill categories — applied to PR DIFF only (light scan). PLUS mandatory cross-file authz audits (2.8–2.10) if diff touches org-scoped handlers, authz calls, or Stripe Connect.

Checks:
1. **Secrets/credentials** hardcoded: Stripe `sk_*`, GitHub PAT, AWS AKIA, private keys, API keys in env. CRITICAL.
2. **Raw PII logging**: `console.log(email)`, logger with unhashed `phone`. CRITICAL or HIGH (dev log vs prod persistent).
3. **SQL injection**: string-concatenated SQL, `.raw()` / `.whereRaw` without parameterised array. HIGH usually, CRITICAL if user input flows unfiltered.
4. **XSS / SSRF**: `dangerouslySetInnerHTML` without sanitisation; user-controlled `fetch(url)` without hostname whitelist. HIGH.
5. **Auth/RLS bypass**: missing auth guard; server action checking role AFTER DB write; service_role key on client. CRITICAL.
6. **Destructive operations + missing guardrails**: DROP TABLE / TRUNCATE without `NODE_ENV !== 'production'` check; `fs.rm(force:true recursive:true)` with user path.
7. **Dangerous URLs**: new DB URLs pointing to prod-looking hosts (`*.rds.amazonaws.com`, `*.supabase.co`, `*.neon.tech`) — HIGH, require confirmation.
8. **MANDATORY cross-file — raw cookie org check vs membership-validated context (CRITICAL/HIGH)**. DO NOT AGGREGATE procedure results — analyse each procedure SEPARATELY.
   - **First**: List ALL NEW/MODIFIED procedures in router (e.g. bookingRouter.ts has `refundOrder` mutation + `getEligibleForRefund` query + `getBookingRefundStatus` query → 3 procedures = 3 independent audits).
   - **For EACH procedure (READ and WRITE)**: if handler uses `ctx.activeOrgId` / `ctxOrgId` / `active_org` cookie to gate with `row.org_id` (e.g. `if (ctxOrgId && refundContext.orgId !== ctxOrgId) throw Forbidden`):
     1. Trace `ctx.activeOrgId` origin. Often `active_org` raw cookie — check `server/trpc.ts`, `server/context.ts` ~ lines 30–60.
     2. Search for membership re-validation: `authzService.assertCan(ctx.userId, "org:read"|"org:manage", {type:"org", orgId: rowOrgId}, ctx.authzCache)` OR `OrgContextService.getWhoAmI(userId, activeOrgSignal)` OR membership query confirming `user ∈ org` BEFORE gating?
     3. Buyer fallback path (e.g. `if (row.userId === ctx.userId) allowed`) is acceptable mitigation for buyer-owned data.
   - **Severity per procedure**:
     - **CRITICAL if** it is a **READ** procedure (query `getEligibility`, `getStatus`, detail view) and gating is ONLY cookie↔row comparison WITHOUT validated membership (no assertCan/whoami). Reason: any authenticated user sets cookie → reads cross-org data.
     - **HIGH if** it is a **WRITE** procedure (mutation `refundOrder`, `cancelBooking`) and gating is cookie↔row WITHOUT validated membership, BUT there are downstream guards (DB order locked + authz.assertCan with rowOrgId) as mitigation.
     - **LOW/NO FLAG** only if (a) assertCan called BEFORE gating with row orgId (not cookie), OR (b) whoami revalidated membership, OR (c) all access through buyer fallback path.
9. **MANDATORY — authzService.assertCan 4th arg authzCache threading (HIGH if missing in router-callable service paths)**. If diff contains `.assertCan(userId, permission, resource)`: check signature — accepts `cache?: AuthzCache` 4th optional param? Does router ctx expose `ctx.authzCache`? Trace params router → service. HIGH if router-reachable services call assertCan WITHOUT passing cache (issues fresh isPlatformAdmin DB query per call under default db-caching rule).
10. **Server action / route handler auth ordering (CRITICAL if after writes)**. Authz checks MUST run BEFORE any DB write or side effect. CRITICAL if reversed.

---

### Category 3: 🟠 Architecture / Backend Layering & Repository Boundary Violations + Migration Hygiene (HIGH or MEDIUM)

Checks:
1. **Router layering — NO business logic + NO direct repository instantiation inside procedures (HIGH/MEDIUM)**.
   - **First (mandatory)**: List ALL NEW/MODIFIED procedures in router file.
   - **For EACH procedure (HIGH if violating)**:
     - (a) Body line count (excluding declaration) `> 50 lines` → suspect Router→Service→Repository violation.
     - (b) Repository instantiation INSIDE router file: `new OrderRepository(...)`, or repository imports and direct `.findById(...)` calls WITHOUT passing through Service. **HIGH severity violation** (architecture.md: "Routers must not own data access").
     - (c) Inline arithmetic/window/refund-gate: `15_552_000_000` (ms constants), `if (eventStartAt <= Date.now())`. AND corresponding Service exists with same gates → **HIGH drift risk**.
     - (d) If only inline calculations (no direct repo instantiation) and no equivalent service → **MEDIUM**.
   - Fix: router procedure = 3 lines max: `validate input` → `authorize assertCan(...)` → `call service.someMethod(...)`. Service methods return structs router just passes as response.
2. **Repository-layer bypass writes inside services (HIGH for writes; MEDIUM for reads)**. If diff contains `queryRunner.manager.getRepository(X).update/.insert/.delete`, or raw `.createQueryBuilder(...).execute()` writes inside service (not repository). Architecture rule: "Repositories own all TypeORM querying". HIGH if writes; MEDIUM if read-only.
3. **Entity/enum definitions inside apps** (shared DB package pattern). HIGH if apps define TypeORM entities / duplicate enums / own migrations. All entities should live in shared DB package detected by che-xray. Bypass ONLY if project profile says "no monorepo DB package".
4. **Migration Hygiene — fabricated timestamps + intra-branch consolidation + RLS defaults (HIGH/MEDIUM)**. If `changedFiles[]` has `**/migrations/*.ts` / `**/migrations/*.sql` / `**/db/migrations/*`:
   - **(a) Fabricated timestamps (HIGH)**: Extract 13-digit ms UNIX prefix from EACH migration filename. IF multiple migrations in same branch have ROUND / IDENTICAL LAST 3-4 DIGITS / EXACT spacing (e.g. 1000ms, 10_000ms) → **HIGH**. Reason: `migration:create` CLI generates real-time timestamps (random last digits). Round timestamps = hand-created → violates "Never hand-create migration files" rule.
   - **(b) Intra-branch patching (HIGH)**: M-1 creates enum X, M-2/M-3/... IN SAME BRANCH (same diff) ALTERS same enum with `ALTER TYPE ... ADD VALUE` or DROP + RECREATE → **HIGH**. Reason: branch migrations MUST be consolidated into 1 end-state migration pre-merge.
   - **(c) RLS policy TO PUBLIC default + inconsistent grants (MEDIUM)**: Check SQL RLS policies: `CREATE POLICY name ON table ...` WITHOUT `TO authenticated`/`TO service_role` clause (implies `TO PUBLIC`). Check `GRANT ...`: if policy is INSERT but only `GRANT SELECT` given → policy inert for client roles. **MEDIUM severity**.
5. **New dependency added to package.json/Cargo.toml/requirements.txt/go.mod** AND:
   - Not mentioned in ticket/scope
   - NO justification in PR body
   - Repo search shows similar existing helper/function/module
6. **PR with >30 files changed** WITHOUT clear justification in PR description why it cannot be split. (MEDIUM risk — harder to review, higher hidden bug chance.)
7. **File added outside module area** scope was supposed to touch — scope creep indicator.

---

### Category 4: 🟠 Scope deviation / UI demo vs claimed wiring (MEDIUM — blocking per user spec)

How:
1. Take scope description / ticket ACs.
2. For each changed file: classify implementation.
3. Compare:
   - **Missing from PR** = ACs not implemented → CRITICAL/HIGH
   - **Added to PR but never mentioned** = scope creep → MEDIUM, must justify.
   - Examples:
     - Ticket = "fix login 500" → PR adds "forgot password feature" → SCOPE CREEP, MEDIUM.
     - Ticket = "add event search" → PR skips pagination AC → MISSING, HIGH.
4. **UI demo simulation vs misleading commit/AC claim (HIGH if mismatch)**.
   - **First (mandatory)**: List ALL NEW `.tsx` files, especially matching feature ticket (e.g. ticket "Process a refund" → `*Refund*Action.tsx`, `*Refund*Dialog.tsx`). For EACH, run **MANDATORY 5-PASS PROCEDURE**:
   - **Pass A — Fake latency scan**: regex match `/setTimeout\s*\(\s*r\s*=>\s*\{?\s*\}|await\s+new\s+Promise\s*\(\s*(?:r|resolve)\s*=>\s*.*setTimeout|sleep\s*\(\s*1\d{3}\s*\)/` in body. If match → A = YES.
   - **Pass B — Simulated failure scan**: regex match `/Math\.random\s*\(\s*\)\s*<\s*0\.\d+/` (e.g. `Math.random() < 0.1`). If match → B = YES.
   - **Pass C — Discarded generated key scan**: regex match `/void\s+(?:idempotencyKey|uuid|key|nonce|generatedKey)\s*[;,]/` or variable generated with `crypto.randomUUID()` / `ulid()` / `nanoid()` and never used in API call param. If match → C = YES.
   - **Pass D — Toast success/fail WITHOUT backend call**: Search for `toast.success(` / `toast.error(` / `toast.info(`. WITHIN 10 lines ABOVE, is there `api.xxx.useMutation` / `mutate(` / `fetch(` / `trpcClient.xxx(` real endpoint call? IF toasts appear WITHOUT ANY backend call in handler → D = YES.
   - **Pass E — Demo data source scan**: Search for `/demoBookings|demo-data|mock-data|seed-demo/` imports in component, or variables named `demoXXX`, `mockXXX` used as data source (not test fixtures). If match → E = YES.
   - **Severity check**: IF (A OR B OR C OR D) YES **AND** (commit/PR/ticket ACs) claim feature is "wired to backend" / "complete UI integration" / not "demo/scaffold" → **HIGH severity finding**. Reason: misleading commit makes reviewer/PM think feature integrated when it's fake.
   - Fix: (1) wire handler correctly (call tRPC mutation with generated idempotencyKey, gate visibility with service call), or (2) prominent DEMO label and separate from shipping code (move to `components/demo/*` + `// TODO REMOVE BEFORE SHIP`).
5. **4.7 Test-suite naming + comment self-containment check (RULE 7.9, MEDIUM / WARN).**

   **🔴 HARD RULE — PROHIBITED INVERSION (NEVER do this):**
   > ❌ **WRONG:** Complain that a test DOES NOT have `FLO-xxx` / `T<N>` / `AC<N>` in title.
   > ✅ **CORRECT:** Having these references IN THE TITLE OR IN A COMMENT is ANTI-PATTERN (bad). NOT having them and describing ONLY observable behaviour is GOOD / COMPLIANT.
   >
   > **1-sentence decision:** `Title or comment contains FLO-ID? → BAD = FINDING. Neither contains an ID? → GOOD = NEVER report finding for this.`
   > **Self-contained comment (NOT a violation):** doc comment describing arrangement, input, expected result and invariant — with NO `@ticket` / `@ac` / `@task` / `@spec` tags.

   Scan added/modified test files (`*.test.*`, `*.spec.*`, `__tests__/`). Detect anti-patterns in the **TITLE STRING** of `describe("...")` / `it("...")` / `test("...")` **and in the comment/JSDoc block attached to it**:
   - Ticket IDs: `FLO-\d+`, codes like `ABC-123` (ANY 2+ letters prefix + hyphen + number = BAD)
   - Task/item IDs: `Task? T\d+(\.\d+)?`, `Item \d+`
   - AC/section IDs: `AC\d+`, `§\d+(\.\d+)?`, `REGRA \d+`, `SPEC_XXX`, `PRD §`
   - Phase/story IDs: `Fase \d+`, `Story #?\d+`
   - Planning anchors: `@(ac|task|ticket|spec|bug)\b`, `B-\d+` / `AB-\d+`

   Severity (FINDING = BAD title/comment = contains patterns ABOVE):
   - 1–4 bad titles/comments → **LOW WARN** (non-blocking, "Nice-to-have" list)
   - 5–9 bad titles/comments → **MEDIUM** (main findings; rename required or explicit override)
   - ≥10 bad titles/comments → **HIGH** (blocking: CI report useless, breaking rule at scale)

   **❌ NEVER generate finding for "missing FLO-xxx in title"** → Desired behavior, compliant. Any report flagging missing task-id in title is a REGRESSION, invalidates section.

   Never flag a self-contained doc comment as bad. Never ask for a traceability anchor to be added — traceability belongs to the SPEC §5 matrix and the PR body, not to the code.
6. **4.8 Route-level / failure-path test gap check (MEDIUM if missing)**. If Category 0 found new webhook route event type → require 1 route-level signed-payload POST test. If Category 0.3 flagged tx pattern → require 1 failure path test: Stripe 5xx → tx rollback + retry with same idempotency key → no double-effect. MEDIUM (waivable ONLY with PR body sign-off override).
7. **4.9 Application-code comment self-containment (RULE 7.9, LOW / MEDIUM).**
   - Scan added/modified **non-test** files (`*.ts`, `*.tsx`, `*.py`, `*.go`, `*.sql`, `*.sh`, `*.toml`, `*.yml`): every comment (`//`, `#`, `/* */`, docstring).
   - **BAD (LOW each, MEDIUM when ≥5 in the diff):** a comment whose meaning depends on a planning artefact — `// AC-3: validate refund`, `// T2.4`, `// B-2 idempotency`, `// SPEC_xxx`, `// see §4.2`, `// TODO(FLO-789)` with no stated reason.
   - **ALLOWED:** the same comment **after** a complete explanation, where the ticket id, spec id or external URL is only extra context: `// TODO(FLO-789): batch the writes once the upstream API supports multi-row insert.` Removing the reference must not change the meaning.
   - **Fix:** state the reason or constraint in the comment itself; keep or drop the reference.
   - Never flag a reference that follows a self-contained explanation.

---

### Category 5: 🟡 Design Quality / Ousterhout RED FLAGS (engineering-contracts Appendix D D.1) — HIGH if RF01-RF04, MEDIUM if RF05-RF13

Appendix D canonical source → `skills/engineering-contracts/SKILL.md`. Never flag patterns explicitly requested in ticket scope (downgrade to NIT waivable ONLY if scope explicitly asked for abstraction shape).

**How to apply (never guess — diff-based):**

1. **RF01 — Shallow Module / Class / Abstraction (HIGH if NEW abstraction, 3+ files depend, API surface > implementation lines)**.
   - Trigger: Diff adds NEW exported `class X`, `interface X`, `abstract class X`, `createXService()` factory, or `useX()` hook, AND: (a) abstraction has `> 8 public methods` OR (b) 3+ OTHER files in diff import from it, AND (c) total implementation LOC ≤ 1.2× public API surface LOC. Ousterhout #1 red flag: "new abstraction adds complexity without hiding any."
   - Downgrade to NIT if: scope file / task envelope explicitly says "create this interface / generic hook for future reuse."

2. **RF02 — Information Leakage across boundaries (HIGH if cross-package / cross-layer)**.
   - Trigger (scan imports + args):
     - Service in `packages/foo/src/services/x.ts` imports DATABASE-SPECIFIC type (e.g. `QueryRunner`, `EntityManager`, `SupabaseClient`) and exposes in public param or return type → caller must know DB engine = HIGH leakage.
     - Backend handler returns internal DB entity CLASS directly (not pick/omit/DTO) including internal fields (e.g. `stripeIdRaw`, `authzCache`) → frontend knows backend schema = HIGH.
     - Config parsing details (zod schema field names, `process.env.KEY`) leak into component/service (not just typed config object) = MEDIUM.

3. **RF03 — Pass-Through Method / Handler Chain (HIGH if ≥3 layers deep with NO logic)**.
   - Trigger: Find call chain `router.foo → service.foo(...args) → repository.foo(...args) → ...` where 2+ consecutive layers do NOTHING except pass same args (no validation, authz, mapping, idempotency key, error wrapping). HIGH per chain depth ≥3 with ZERO added value. If one layer adds authz or input validation only → MEDIUM (suspicious but not pure passthrough).

4. **RF04 — Temporal Decomposition (HIGH if business concept split by PHASE instead of ENTITY)**.
   - Trigger (file structure): If scope "process refund" → diff creates `RefundStep1Validate.ts`, `RefundStep2StripeCall.ts`, `RefundStep3UpdateDB.ts`, `RefundStep4EmitEvent.ts` with NO `RefundService.ts` / `Refund aggregate` owning concept + invariants. Grouped by WHEN they run instead of WHAT concept → HIGH. Correct: one module owns concept and invariants, exposes method orchestrating steps internally.

5. **RF05 — Repetition / Near-Duplicate Logic (MEDIUM if 2+ blocks, NIT if just formatting)**.
   - Scan for 2+ blocks with `≥ 12 identical token sequences` in different files (not test fixtures). MEDIUM unless scope explicitly says "ship fast with duplication, DRY in follow-up" (documented in PR body).

6. **RF06 — Over-generic `<T>` with exactly 1 concrete caller (MEDIUM)**.
   - Trigger: Diff adds `class Foo<T>` / `function bar<T>()` / `interface X<T, U, V>` with 3+ generic params, AND EXACTLY 1 concrete instantiation in repo. If scope mentions "reused in epic Y" → downgrade to LOW waivable.

7. **RF07 — Comment / Over-comment Explaining WHAT, not WHY (MEDIUM if masking complexity)**.
   - Trigger: `/* 5+ line comment block */` literally restating next 5 lines in English. If code needs that much WHAT-comment → abstraction wrong; rename functions/extract helpers. MEDIUM only if total comment-LOC ≥ implementation-LOC.

8. **RF08-RF13 — Secondary flags (all MEDIUM, grouped):**
   - RF08: Boolean-flag hell = `≥ 4 boolean params` (prefer 2 separate functions / 2-max strategy).
   - RF09: Conjoined methods = one public function doing two unrelated things with single shared error path (split).
   - RF10: Config explosion = `≥ 5 new YAML/env vars` for ONE feature without justification (default-first).
   - RF11: Unused generality = NEW exported param, optional overload, or interface method with ZERO callers and no mention in scope.
   - RF12: Wrong naming = class/module name is a VERB (e.g. `ProcessRefund.ts`) not a NOUN owning responsibility (e.g. `RefundService`).
   - RF13: Hidden side effect in getter/helper = `getX`, `loadX`, `findX`, `formatX` actually WRITES / MUTATES / EMITS internally.

**HARD RULE for ship integration §0.9.2 (≤ 2 HIGH auto-fix contract):** ANY Category 5 HIGH finding (RF01-RF04) counts TOWARD the "≤ 2 HIGH total" threshold.

---

### Category 6: 🟡 Logging & Observability Anti-Patterns (engineering-contracts §12 + §20) — HIGH for PII/raw-secret leaks, MEDIUM for verbosity/signal/levels

> **Canonical source:** `engineering-contracts/SKILL.md` §12 + §20. Apply to any diff adding/changing logger/console/echo calls, IO flows, shell scripts, CI workflows, or logger config. Cite EXACT anti-pattern ID.

**How to detect:**

1. **L6.1 🔴 CRITICAL / HIGH — Raw PII / secrets in log output.** Diff contains literal `console.log(email)` / `logger.info({ phone })` / `echo "$user_input` or logger call with raw `email`, `phone`, `address`, `stripe_id` (unhashed), credit card, SSN, `sk_*`, `AWS_SECRET_ACCESS_KEY`, raw JWT, API keys in full env dump. Rule §20.6. Use hash/mask/omit.
2. **L6.2 🟠 HIGH — Wrong level: error as info or debug floods.** E.g.: `logger.info(">>> ENTERING function foo")` on EVERY internal call (noise); `console.error` for expected handled branch; logger.debug with full request payloads on prod (leak volume).
3. **L6.3 🟡 MEDIUM — Missing structured correlation fields.** Logs as free-form string `"User did X"` without context. Missing: `traceId`, `spanId`, `correlationId`, `orgId`, `userId`, idempotency key, structured `operation` or `event` fields.
4. **L6.4 🟡 MEDIUM — Script / bash / CI workflow without expressive logging.** New shell script (>30 lines) without echo in IO steps or `set -x` flood ALONE without semantic messages. Or echo without prefixed `[INFO]` / `[WARN]` / `[ERROR]` levels.
5. **L6.5 🟡 MEDIUM — Flood / loop log / verbose hot path.** Inside loop N > 100, each iteration logs info; or hot path (<1ms) has 3+ logger calls; or full JSON stringify of large arrays without truncation. Rule 20.7 "No Flood Volume".
6. **L6.6 🟡 MEDIUM — Did not follow repo existing logger wiring.** Repo has `@flockr/logger`, `@/server/logger.ts`, `OTEL provider`, `pino`, etc. — but diff writes raw `console.log`. Repo convention not followed (§20.4).
7. **L6.7 🔵 LOW — Empty catch block logging without context.** `catch(e) { console.log("it failed") }` without structured error, message, stack, or request ID. Better: `logger.error({ err, op: "refund.create" })`.

**Default severity:**
- L6.1 or raw secrets → CRITICAL if prod log; HIGH if only dev console; HIGH anyway;
- L6.2 / L6.5 = HIGH if failure of bad level;
- Others → MEDIUM default;

**MANDATORY Coverage table row:** "Coverage of Review" must include "✓ Yes — 8 categories" for Category 6.

---

### Category 7: 🟢 Testing Gaps & Regression Lock (QA-Centric ONDA1) — HIGH for missing tests, MEDIUM for planning references in tests, LOW for skip without ticket

> **Enforcement companion:** che-debugger-bugfix Step 1.2.5 REPRO AUTOMATION LOCK enforces SAME rules for bug-fix. Category 7 applies for feature diffs touching runtime behaviour / routes / UI.

**How to detect (diff-based, cross-check changed files against `*test*`, `*spec*`, `__tests__/` additions):**

1. **G7.1 🟠 HIGH — ≥20 added lines of runtime behaviour code WITHOUT test file added/modified.**
   - Compute: from `changedFiles[]`, count ONLY lines ADDED (`+` prefix) in files under `src/`, `server/`, `app/`, `packages/*/src`, `components/` (exclude types, interfaces, enums, re-exports, configs, migrations).
   - Also count ONLY files matching `*.test.*`, `*.spec.*` inside `__tests__/`, `test/`, `spec/`.
   - If behaviour additions ≥20 lines AND test file count added/modified = 0 → **HIGH G7.1 = MISSING TESTS FOR NEW BEHAVIOUR.**
   - **EXEMPTIONS (waive only if body match):**
     - `refactor:` commit AND body includes `"renames only"` or `"no behavior change"` — and diff is only renames.
     - `style:` commit (formatting, whitespace, CSS-only).
     - `docs:` / `chore(ci):` / `chore(deps):` bump-only — and ZERO runtime src/ files changed.
     - Commit body has EXPLICIT `QA_OVERRIDE: "no test possible here: <1-line justification>"` signed-off in PR body.
   - **Fix:** Add behavioural spec (unit preferred, integration if ≥2 modules; route-level for REST/tRPC; Playwright for UI). Min 1 happy + 1 sad path per new exported function / route mutation.

2. **G7.2 🟠 HIGH — Public API change OR interactive UI component added without integration/Playwright test.**
   - **Branch A (Public API):** Diff touches tRPC router (e.g. `server/api/routers/xRouter.ts` mutates) or REST handler (`route.ts`, `app/api/*/route.ts`, `server/webhooks/*`) OR new exported function from public `exports` field. AND no addition/modification of route-level test (`*.api.test.ts`, `__tests__/e2e/*`). → **HIGH G7.2a.**
   - **Branch B (Interactive UI component NEW):** Diff adds NEW `.tsx` exporting user-visible interactive component (Button/Dialog/Form/Modal/Tabs/Table/AutoComplete — keywords or JSX handlers `onClick`, `onSubmit`, `onChange`, `useState`, `useMutation`). AND no RTL/Playwright spec exists. → **HIGH G7.2b.**
   - **Exemptions:** explicitly marked DEMO/SCAFFOLD (`*Demo*.tsx`, `*Scaffold*.tsx`) + PR body warning. OR strictly internal / health-check (`/healthz`).
   - **Fix:** Add 1 route-level test (API branch A) calling `trpcClient.xxx(...)` / `POST /api/xxx` with signed payload + valid auth; for UI add 1 RTL spec calling `fireEvent.click` + assertions.

3. **G7.3 🟡 MEDIUM — Planning artefact referenced inside a test (title or comment).**
   - Scope: scan EVERY new/modified test file (`*.test.*`, `*.spec.*`). Check the `describe()` / `it()` / `test()` title string AND the comment/JSDoc block attached to it.
   - Detect regex: `@(ac|task|ticket|spec|bug)\b`, `\b(AB|B)-\d+\b`, `FLO-\d+`, `Task? T\d+(\.\d+)?`, `AC\d+`, `§\d+(\.\d+)?`, `SPEC[_-]\w+`.
   - If any match → **MEDIUM G7.3 default = EXTERNAL REFERENCE IN TEST.**
   - **Exception:** pure test infra refactor (rename, package.json, jest/vitest config). Ticket IDs in the *filename* are governed by the G5 regression-folder policy below, not by this check.
   - **Fix:** rewrite the title as observable behaviour and replace the anchor with a self-contained doc comment (arrangement, input, expected result, invariant). Traceability moves to the SPEC §5 Verification Matrix and the PR body.
   - **🔴 AUTOMATIC SEVERITY UPGRADE TO HIGH (G5 cross-cutting exception):** IF (test located in **`tests/regression/<TICKET_ID>--<slug>.test.ts` (with ticket ID in filename) AND NO `EXPLICIT_OVERRIDE_G5_REGRESSION_FOLDER` logged in decisions.log.jsonl justifying ≥4 independent domains OR pure infra**) → **G7.3 automatically becomes 🟠 HIGH severity** (counts toward §0.9.2 ≤ 2 HIGH auto-fix rule). If test is colocated in the feature folder → no upgrade.

4. **G7.4 🔵 LOW — `.skip()` / `xit()` / `it.todo()` used WITHOUT a stated reason.**
   - Scan for `.skip(`, `xit(`, `it.todo(`, `test.skip(`, `test.todo(`.
   - Check 10 lines around for a comment that explains WHY it is skipped in self-contained terms: `// Skipped: the payments API does not expose partial refunds yet`. A ticket id may follow as extra context (`// TODO(FLO-123): …`) but is not a substitute for the reason.
   - If `.skip` exists WITHOUT a stated reason → **LOW G7.4 = SKIPPED TEST WITH NO EXPLANATION.**
   - **Exception:** `it.skip` inside Scratch `.test.ts` named `scratch.*` or `_WIP_*` (flag only if staged for commit).
   - **Fix:** state the blocking reason above the skip (ticket optional). OR remove skip and make test pass.

**Severity defaults for ship-gate threshold (§0.9.2 auto-fix rule ≤ 2 HIGH):**
- G7.1 + G7.2 = HIGH (BLOCKING if total HIGH ≥ 3 with other Category 0-8 HIGHs; if ≤ 2, auto-fix triggers).
- G7.3 = MEDIUM.
- G7.4 = LOW.

**Coverage of Review /report MUST include Category 7 in table.**

---

### Category 8: 🟣 UI Selector Contract Hygiene & data-testid 3-part Convention (QA-Centric ONDA1) — HIGH for fragile selectors or NEW interactive components w/o ids, MEDIUM for naming, LOW for duplicate list row ids

> **UI selector contract rule source:** che-spec SbE §4.2 Behavior Tables — "UI Selector Contract" column binds Playwright/RTL tests to stable ids. Testing Library Priority Order: **ByRole > ByLabelText > ByPlaceholderText > ByText > ByDisplayValue > ByAltText > ByTitle > ByTestId (last escape hatch)**. When ByRole stable AND unique → data-testid NOT required. Purpose of data-testid: cover UI with unstable/translated/no accessible text: toasts, icon-only buttons, spinners, loading, table row actions.

**MANDATORY `data-testid` convention (3-part kebab-case with double-underscore):**
```
<domain>__<component-or-screen>__<action-or-element>
```
Examples:
- `creator-bookings__refund-dialog__confirm-button`
- `public-events__event-card__buy-now-button`
- `scanner__scan-screen__qr-input`
- `auth__login-form__submit-btn`
- (repeated list rows: append `--<unique-id>`) `creator-bookings__row__refund-button--order-abc123`

Anti-patterns (flag G8.3):
- ❌ `refundButton` (no separator; camelCase not kebab)
- ❌ `creator_bookings_refund` (single underscore)
- ❌ `bookings--refund--button` (triple hyphen not part separator)
- ❌ `cancel` (too generic, 0 parts, no domain context)

**How to detect (8.1 → 8.4):**

1. **G8.1 🟠 HIGH — NEW interactive/visible component (or NEW screen) WITHOUT data-testid on elements that NEED it.**
   - Compute: from changedFiles, list status `A` (added) `.tsx` / `.jsx` / `.vue` OR `.tsx/.jsx` exporting new components (filename includes `Button`, `Dialog`, `Modal`, `Form`, `Tabs`, `Select`, `Combobox`, `DatePicker`, `AutoComplete`, `Dropdown`, `Drawer`, `Snackbar`, `Toast`, `Card`, `Input`, `Table`, `Alert`).
   - For EACH NEW interactive element in JSX:
     - Is `ByRole + accessible name (label/text)` provably stable AND unique? → EXEMPT (Button with static text `<button>Confirm Refund</button>` → no id, `getByRole('button', {name: 'Confirm Refund'})` stable).
     - Is element icon-only button? `<Button><TrashIcon/></Button>`? Loading spinner? Toast? Progress bar? Empty-state? Table row action icon? → DATA-TESTID REQUIRED.
     - Does text change based on i18n / feature flags / dynamic state? → `ByText` fragile → DATA-TESTID REQUIRED.
   - If ≥1 such element in NEW component lacks `data-testid=""` → **HIGH G8.1 = NO SELECTOR CONTRACT FOR FRAGILE ELEMENTS.**
   - **Exemption:** pure presentational `<div>` wrapper with ZERO handlers/interaction. Or PR body explicit QA_OVERRIDE: `G8.1 WAIVED: all content has stable ByRole + accessible names`.
   - **Fix:** Add `data-testid="<domain>__<component>__<element>"` for every element failing stability check. For icon buttons, prefer aria-label FIRST (for screen readers), THEN data-testid as secondary.

2. **G8.2 🟠 HIGH — NEW/MODIFIED TEST FILE uses FRAGILE PRIMARY selector: CSS class, XPath, nth-child(N), regex text, or indexed getAllByRole.**
   - Scope: scan EVERY NEW or MODIFIED test file (`*.spec.ts`, `*.test.tsx`, inside `playwright/`, `e2e/`, `__tests__/`).
   - Flag HIGH if PRIMARY selector (1st element-fetch in 1st/2nd line of test block, or action selector e.g. `click()`/`fill()`) uses anti-patterns:
     - CSS class: `.css-class-name` → ❌ `page.locator('.btn-primary')`
     - XPath: `//div[2]/button[3]` or any `//` prefix → ❌ (structure change = break)
     - `nth-child(N)` / `.getAllByRole('button')[3]` / `.first()` / `.nth(N)` when N≥1 on a list — ❌ (order change = break)
     - `getByText(/partial.*regex/)` with vague regex matching 2+ elements (false-positive risk).
   - **ALLOWED EXEMPTIONS for G8.2 (waive if verified):**
     - Playwright `getByRole('button', { name: 'Save changes' })` — stable unique accessible role + name → ALWAYS ALLOWED (preferred over data-testid).
     - RTL `screen.getByLabelText('Email address')` on labeled inputs → stable → ALLOWED.
     - `getByTestId('creator-bookings__refund-dialog__confirm-button')` valid 3-part convention → ALLOWED.
   - **Fix:** Rewrite to `getByRole(...)` (preferred if stable unique accessible name) ELSE `getByTestId('<valid 3-part id>')`. For lists, use `--<unique-id>` suffix + `getByTestId('x-row__action--' + rowId)`.

3. **G8.3 🟡 MEDIUM — data-testid attribute exists but DOES NOT follow 3-part convention.**
   - In NEW files: any `data-testid="..."` failing regex: `^[a-z0-9][a-z0-9-]*__[a-z0-9][a-z0-9-]*__[a-z0-9][a-z0-9-]*(--[a-z0-9][a-z0-9-]*)?$`.
   - In MODIFIED files: only flag `data-testid` WRITTEN/CHANGED in this diff (not legacy dirty ids).
   - If non-conforming id exists AND file not LEGACY → **MEDIUM G8.3 = NON STANDARD TEST ID FORMAT.**
   - **Exception:** Explicit `G8.3 CONVERTED LATER: <ticket>` in PR body for follow-up refactor batch.
   - **Fix:** Rename to canonical `domain__component__element[--unique-row]`. Update all spec file references.

4. **G8.4 🔵 LOW — Duplicate identical data-testid in list/tabular renders without per-row unique suffix.**
   - Pattern: Inside `.map()` / loop (JSX lists, tables, grid rows, tab panels), SAME data-testid emitted for EACH row without row-distinguishing suffix.
   - Example flagged: `<Button data-testid="orders__table__cancel-button">` inside `orders.map(...)` (10 rows = 10 identical ids → `getByTestId` throws `Found multiple elements`).
   - Correct (waive): `<Button data-testid={'orders__table__cancel-button--' + order.id}>`
   - If duplicate exists → **LOW G8.4 = AMBIGUOUS DUPLICATE TESTID IN LIST.**
   - **Fix:** Append `--` + unique entity primary key to 3-part canonical id.

**Ship threshold enforcement for G8 findings:**
- G8.1 + G8.2 = HIGH (both count toward §0.9.2 ≤ 2 HIGH ship rule).
- G8.3 = MEDIUM.
- G8.4 = LOW.

---

## 3. NON-goals (we explicitly skip these — DO NOT waste tokens / time)

- ❌ Biome / formatting / indentation issues. (Lint CI job.)
- ❌ Naming nitpicks: `myVar` vs `my_variable`. **EXCEPTION:** naming of test-suite `describe()` / `it()` / `test()` titles (Category 4.7 behavioral check).
- ❌ Test coverage% alone (check if tests MISS for CRITICAL code, but don't demand lines).
- ❌ Documentation README unless actively misleading about security/usage.
- ❌ TODO/FIXME comments (unless for auth/security debt).
- ❌ General refactors not risking correctness.

---

## 4. Output — Structured Review Report (English for files/code refs, Portuguese for user narrative)

Follow template: `references/REVIEW_REPORT_TEMPLATE.md`

**MANDATORY SECTIONS ORDER (DO NOT skip any):**

**1. Header (mode-dependent):**
- Mode A (PR URL): `# Review Report — PR #<PR_ID>: <title>`
- Mode B (Worktree Local): `# Review Report — LOCAL WORKTREE MODE` then `## Context` with subfields:
  - Worktree path: `<WORKTREE_ROOT>`
  - Current branch: `<BASE_BRANCH_HEURISTIC>`
  - Changed files count: `<changedFiles_count>`
  - Diff stat: `<+additions / -deletions>`
  - Changed files list (table: Status | Path | +/- lines)

**2. Executive Verdict** (template section — do not skip):
- 🔴 Request changes (≥1 CRITICAL or ≥2 HIGH) / 🟡 Approve with comments / 🟢 Approve
- Blocker tally table: CRITICAL / HIGH / MEDIUM / LOW — counts

**3. Context Bootstrap Evidence TABLE** (MANDATORY — never empty):
- Fill template table. Each §1.5 item (resolver run, R1-R6 context reads, cross-file pipeline reads, local skill absorbed). If a file does not exist = "(N/A — file non-existent in repository)". DO NOT leave blank lines.

**3.5 ⚖️ Rule Resolution** (MANDATORY — one block, never per finding):
- `Sources`: `<n>` read, `<n>` applicable, `<n>` path-scoped out, `<n>` below `min_severity`.
- `Params in force`: min_severity / blocking / ignore_paths / max_rules.
- `Precedence`: one line per `kind: precedence` conflict — winner and loser with citations.
- `Drift`: one line per `drift` entry (repo rule ≠ Che project memory).
- `Unresolved conflicts`: one line per `kind: unresolved` — both citations + "capped at MEDIUM".
- If there were no conflicts: say `no contradictions detected` explicitly (never omit the block).

**4. Findings section:**

For each finding (both modes identical from here):
- Severity: 🔴 CRITICAL / 🟠 HIGH / 🟡 MEDIUM / LOW WARN NON-BLOCKING
- Category: Pipeline Integrity / Runtime / Security / Architecture / Scope / Design Quality (Ousterhout)
- File:line
- Snippet (3 lines before + 3 lines after, from patch)
- Why this is a problem (evidence-based — never "I don't like it")
- **Explicit rule citation (MANDATORY when possible)**: quote EXACT `source:line` from the resolver's `rules[]`. E.g.: "violates [architecture.md](file:///.../.claude/rules/architecture.md#L12) 'Router → Service → Repository: Routers must not contain business logic >30 lines'". NEVER cite a rule whose `superseded_by` is set. A rule with `conflicted: true` is cited with BOTH sides and capped at MEDIUM. Category 5: ALWAYS cite `engineering-contracts/SKILL.md` Appendix D D.1 with RF number.
- Actionable fix — specific lines/what should replace
- Optional: suggest code change snippet ONLY if obvious. NEVER rewrite whole file.

**N-1. Coverage of Review TABLE** (MANDATORY — user trusts audit):
- 7 mandatory rows: §1.5 Rule Resolution → Category 0 Pipeline Integrity → Category 1 Runtime → Category 2 Security+PII+Authz audit → Category 3 Architecture/Repo boundary → Category 4 Scope deviation / Demo UI / Test naming → Category 5 Design Quality / Ousterhout RF01-RF13
- Non-goals (style/format/coverage%) → Skipped intentionally note.

**N. Final verdict section (template):**

At the end (both modes, except verdict notes):
- **Verdict**: 🔴 Request changes (≥1 CRITICAL or ≥2 HIGH) / 🟡 Approve with comments (only MEDIUMs/LOWs) / 🟢 Approve
  - **Mode B NOTE**: Verdict labels refer to "if this were submitted as a PR". Since local work-in-progress, interpret as: 🔴 = Fix before committing/pushing; 🟡 = Fix before merging; 🟢 = Clean.
- **Blocker summary**: numbered list — each CRITICAL/HIGH fixed before merge (or before commit+push in Mode B)
- **Non-blocker nice-to-have**: numbered list — MEDIUM/LOW, fix or ignore, user decides

**O. 🎯 ACTIONABLE FINDINGS — copy-paste block (MANDATORY — the LAST section of the report)**

> Purpose: every finding becomes actionable in one paste. This is the section the user actually copies from, so it must be self-contained — the reader should never have to scroll back to "Findings".

One entry per finding, in the SAME ORDER as the Findings section (blocking severity first). If a finding is skipped because it needs no code comment (already answered in the PR body, or a pure question), say how many were skipped and why.

Canonical entry — five fields, nothing else:

| Field | Rule |
|---|---|
| **Finding + category** | `#F-<n> · <severity> · <category>` — the ID and category MUST match the Findings section verbatim. |
| **Where** | `path/to/file.ext:LINE` — the exact line the comment will attach to. |
| **Explanation** | 1–3 lines for the USER (Portuguese in chat). Why it is a problem, in plain language. |
| **GitHub comment (EN)** | MAX 2 sentences, simple English, no jargon. This is the literal posted text: state the consequence, not the rule number. |
| **Post command** | The `gh api` command below, filled in. |

```bash
# Post ONE inline review comment pinned to an exact line (Mode A only).
# side=RIGHT → LINE is the line number in the NEW file (added or context line).
# side=LEFT  → LINE is the line number in the OLD file (a deleted line).
# -F line=N is a TYPED (integer) field; -f is for strings. Swapping them sends a
# string and GitHub rejects the request.
gh api repos/<OWNER>/<REPO>/pulls/<PR_NUMBER>/comments \
  -f body='<the 2-sentence English comment>' \
  -f path='<path/to/file.ext>' \
  -F line=<LINE> -f side='RIGHT' \
  -f commit_id="$(gh pr view <PR_NUMBER> --repo <OWNER>/<REPO> --json headRefOid -q .headRefOid)"
```

HARD RULES for the post command:

1. **The line MUST appear in the PR diff.** GitHub accepts a comment only on a line inside a hunk (an added line, or a context line within a hunk). A line outside every hunk returns `422 Validation Failed`. When the finding is about code that is NOT in the diff, pin the comment to the nearest in-diff line and say so in the body, or post it as a PR-level comment instead.
2. **`side` must match where the line lives.** `RIGHT` for the new side, `LEFT` only for deleted lines. The wrong side highlights the wrong line, or fails with 422.
3. **Never guess the line number.** Read it from the hunk header (`@@ -old,len +new,len @@`) or from the file at the PR head commit. A comment pinned to a guessed line teaches the author to distrust the tool.
4. **Two sentences maximum.** If it does not fit in two, the finding is not understood well enough yet — go back to the analysis.
5. **No single quotes inside `-f body='...'`.** An apostrophe in English prose ("doesn't", "won't") breaks the shell string. Use the quote-safe form below when the comment needs one.
6. **Multi-line findings** (a whole function rather than one line): add `-F start_line=<FIRST> -f start_side='RIGHT'`. `line`/`side` stay the END of the range.
7. **Mode B (local worktree) has no PR.** Emit the same five fields, but leave the command in placeholder form with the note "run once a PR exists". NEVER fabricate a PR number.
8. **Never post automatically.** These commands are generated FOR the user; posting happens only when the user explicitly asks (§5).

Quote-safe form for rule 5 — reads the body from stdin, so no quoting hazard:

```bash
gh api repos/<OWNER>/<REPO>/pulls/<PR_NUMBER>/comments \
  -f path='<path/to/file.ext>' -F line=<LINE> -f side='RIGHT' \
  -f commit_id="$(gh pr view <PR_NUMBER> --json headRefOid -q .headRefOid)" \
  -F body=@- <<'EOF'
Since `applyDiscountCode` no longer patches the PaymentIntent server-side, this total is only what the buyer sees.
EOF
```

**Chat delivery:** the five fields per finding — Portuguese for the explanation, English for the GitHub comment body, and the command verbatim. This block IS the deliverable: do not also paste the full report.

---

## 4.9 🔴 MANDATORY STORAGE PREFLIGHT (NEVER SKIP — engineering-contracts §20 + CHE_RULES.md STORAGE BOUNDARY)

> **USER VERBATIM HARD STOP RULE:** No che work asset should be created in the worktree. Only when explicitly requested. Everything should be organised in che-sessions.

**BEFORE FIRST disk write (report, screenshots, decisions, QA evidence, etc.), RUN EXACTLY THIS BLOCK:**

```bash
# (1) Resolve the `che` CLI (owns the Che-home cascade + canonical path construction)
command -v che >/dev/null 2>&1 || { echo "❌ FATAL: 'che' CLI not found on PATH. Cannot write outputs without storage boundary. Aborting write."; exit 98; }

# (2) Define minimum variables for binding
SESSION_ID="${CHE_CURRENT_SESSION_ID:-${CHE_SESSION_ID:-fallback-review-session}}"

# (3) Compute canonical paths + ensure base dirs (SESSION_DIR, WORKSPACE_SHARED, etc.)
if [ -n "${WORKTREE_ROOT:-}" ] && [ -d "$WORKTREE_ROOT" ]; then
  eval "$(che compute_paths "$WORKTREE_ROOT" "$SESSION_ID" --cwd "$PWD")"
  che ensure_dirs "$WORKTREE_ROOT" "$SESSION_ID" --cwd "$PWD"
  # Double-guard: `che output_path` already runs assert automatically; reaffirm here for clarity
  che assert_outside_worktree "$CHE_SESSION_DIR" "$WORKTREE_ROOT" --label "CHE_SESSION_DIR (ephemeral root)"
  che assert_outside_worktree "$CHE_WORKSPACE_SHARED" "$WORKTREE_ROOT" --label "CHE_WORKSPACE_SHARED (durable root)"
fi

# ⚠️ AFTER this block, DO NOT construct paths manually.
# ALWAYS USE: OUTPUT_PATH="$(che output_path "<type>" "<slug>" "<related_id>" "<scope=session|workspace>" "<ext>" "<suffix>")"
```

---

## 5. Post-report actions

> **IMPORTANT: STORAGE BOUNDARY — NEVER write inside worktree. ALL output via `che output_path` only (see §4.9).**

### Mode A (GitHub PR):
- **Construct report path USING HELPER (never manual):**
  ```bash
  # Principal (full) report — related_id = pr-<ID>; grouped in reviews/pr-<ID>/
  REPORT_FULL_PATH="$(che output_path "review" "che-code-review" "pr-${PR_ID}" "session" "md" "full")"
  ```
  - **Expected result:**
    ```
    $CHE_SESSION_DIR/reviews/pr-<ID>/
      ├── 20260902-092400-che-code-review_full.md   (1st round)
      └── 20260902-093000-che-code-review_postfix.md (2nd round)
    ```
  - **Safe fallback WITHOUT binding (rare):** `che output_path` automatically falls back to `$CHE_HOME/outputs/fallback-session/reviews/pr-<ID>/...`; NEVER worktree or `./reports/`.
  - **NEVER use relative path `./reports/` or `$WORKTREE_ROOT/.trae/`. §20 MORATORIUM.**

- **DO NOT approve or request changes DIRECTLY on GitHub via `gh pr review`** unless user explicitly asks after seeing report. First deliverable = report for user to review in chat.
- **The §4-O post commands are NOT run by this skill.** They are emitted for the user to paste, one per finding. Posting inline comments on the user's behalf requires an explicit request ("posta os comentários"), and even then only for the findings the user names.
- If ZERO findings → still write report: "No CRITICAL/HIGH issues found; scope matches; dependencies justified." + list checked items.
- **Write using atomic write:** pipe markdown to `che write_file_atomic "$REPORT_FULL_PATH"` stdin.

### Mode B (Local Worktree):
- **Construct report path USING HELPER:**
  ```bash
  # Worktree slug: extract basename from WORKTREE_ROOT
  WT_SLUG="$(basename "${WORKTREE_ROOT%/}")"
  REPORT_LOCAL_PATH="$(che output_path "review" "che-code-review" "worktree-${WT_SLUG}" "session" "md" "full")"
  ```
  - **Expected result:** `$CHE_SESSION_DIR/reviews/worktree-<WT_SLUG>/20260902-101500-che-code-review_full.md`
- **DO NOT interact with GitHub at all** in Mode B. Pure local output inside che-sessions.
- Zero findings → still write report: "No CRITICAL/HIGH issues found in modified files. Scope matches stated goals; dependencies justified." Include full changed files list + checked categories.
- Optional user convenience at end of chat:
  - If Mode B, after presenting findings, offer ONE follow-up action:
    - `[Apply fixes locally]` — if user says yes, fix CRITICAL/HIGH blockers using che-developer mindset.
    - `[Show just the blocked items condensed]`
    - `[Nothing, thanks]`
