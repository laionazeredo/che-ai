---
name: "harness-code-review"
description: "High-impact code review with TWO MODES: (A) GitHub PR URL as before, or (B) LOCAL WORKTREE MODE when user passes --worktree <path> WITHOUT a GitHub PR URL — reviews files currently in the modification/staging area (git status + git diff). Focuses ONLY on blocking issues: runtime regressions, security/PII leaks, unjustified dependencies, and scope deviations. Invoke when /harness-review is called or user asks for code review."
---

# Harness — Code Review (High Impact Focused)

> **SHARED REFERENCES (CANONICAL — NÃO DUPLICAR corpo aqui):**
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

1. **Read Level1 Global Index FIRST:** Read `$HOME/.trae/bindings/registry.md`. Find LAST STATUS=BOUND entry with current SESSION_ID. Use its WORKTREE_ROOT for the session.
2. **Mode B mismatch check (CRITICAL):**
   - If user passed --worktree <path>: confirm Level1 registry WORKTREE_ROOT EXISTS and is DIFFERENT than <path> → BLOCK.
   - Ask: "You asked review on worktree X but Level1 GLOBAL session is BOUND to Y. Options: (A = X, override binding; B = Switch binding switch first; C = Cancel review). NEVER silent override. If no Level1 entry → binding not made; proceed to decision flow to create binding (§19.2 only if user continues."
3. **Mode A PR URL + local worktree:** PR for branch that resides Level 1 registry says BOUND on some worktree:
   - If PR is for branch worktree B user says --worktree pointing to A → BLOCK. Ask which is correct.
4. **Pre-send trimmer refs (global:** Output final report refs file links MUST NOT span ≥2 worktrees unless user explicitly asked cross-worktree comparison. Mixed trim single scope before send.

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

#### 1.1 PR metadata

```bash
gh pr view <PR_URL> --json \
  number,title,body,state,isDraft,baseRefName,headRefName,additions,deletions,changedFiles,commits,labels,reviewDecision,mergeable,files,author,reviews
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
- **Goal** da tarefa / acceptance criteria list
- **Out-of-scope** / explicit não-faz
- Arquivos esperados / áreas de risco

If no ticket was given, the user's plain text description becomes the scope of reference.

---

### Mode B (Local Worktree) → use git commands directly (NO gh / NO network)

Run ALL of these inside `<WORKTREE_ROOT>` directory. Never leave the worktree.

#### B-1.1 Capture modified/staged/untracked files + diffs

**Step 1: get full file list (union of staged + unstaged + untracked tracked files).**

```bash
# Summary list (short format — for display + counting):
git status --short

# Individual diffs we need for review (combine BOTH staged + unstaged changes):
#   B-1.1.1: staged diff (files already "git add"ed)
git diff --cached --unified=3

#   B-1.1.2: unstaged diff (working tree modifications not yet added)
git diff --unified=3
```

**Step 2: build the canonical file list `changedFiles[]` we review.**
Rules:
1. Parse `git status --short` output (short format flags: `M` = modified, `A` = added, `D` = deleted, `R` = renamed, `??` = untracked).
2. **Include in review list:**
   - Files with status: `M`, `A`, `R`, `C` (copied), `T` (type changed), `U` (unmerged) — both staged and unstaged variants: ` M` (unstaged only), `M ` (staged only), `MM` (both) → all include.
   - `??` (untracked files): **INCLUDE ONLY if they look like code/config (exts: .ts,.tsx,.js,.jsx,.py,.rs,.go,.java,.kt,.sql,.json,.yaml,.yml,.toml,.md where.md is a PRD/spec doc NOT generic README fluff; if user clarifies include extra, honor that).**
   - Skip binary auto-generated build artifacts (node_modules/, dist/, .next/, build/, coverage/, *.png, *.jpg, *.pdf, *.lock diffs auto-generated by package managers — treat as out-of-scope unless scope says otherwise).
3. **For each file in canonical changedFiles[]:**
   - Record relative path, change type (M/A/D/R/??), count lines added/deleted from its diff block.
   - If file is untracked (`??`) AND new → its "patch" = FULL file content (treat as 100% additions diff block): read it whole via `cat`.
4. Aggregate:
   - `changedFiles_count` = N files in canonical list
   - `diff_stat` = total additions / total deletions (sum from B-1.1.1 + B-1.1.2, excluding skipped binaries/locks)
   - `BASE_BRANCH_HEURISTIC`: run `git rev-parse --abbrev-ref HEAD` → current branch name (for info only — no base/head concept locally; base is assumed to be what's committed on this branch before modifications)

#### B-1.2 Ticket context

Same as Mode A 1.2 — parse ticket (if provided) or use user's plain text scope description.
**CRITICAL for Mode B**: because there's no PR body describing intent locally, the ticket + user scope description becomes the ONLY authority for Category 4 (Scope Deviation) classification. Be conservative.

---

## 2. Review framework — 4 categories ONLY

We only look at these 4. Anything else is out-of-scope for this reviewer role.

---

### Category 1: 🔴 Runtime breakage / silent incorrect behavior (CRITICAL if found)

What counts:
- **Possible NullPointer / undefined field dereference** at runtime (access `obj.field.subfield` where `obj.field` can be null/undefined based on the types / DB schema and there's no guard).
- **Race conditions**: async operations with TOCTOU, unhandled Promise rejections, missing `await` on async functions, `Promise.all()` where one fails silently, race on shared mutable state.
- **Wrong algorithm / calculation**: obvious logic errors (if/else swapped, `<=` should be `<`, `+` should be `-`, currency divided by 100 twice so $1.00 becomes $0.01).
- **Schema backwards-incompatible change**: API returns a type that old clients can't handle.
- **Deprecation wrong API usage**: calling a deprecated endpoint / method that the upstream docs say will fail (e.g. Stripe v1 endpoint in a v2-only integration).
- **Missing null/empty handling**: DB returns `[]` for an "empty list" vs `null` for "not queried" and code treats both the same way when they shouldn't be.
- **Boundary conditions**: off-by-one, array index `-1`, pagination last page truncated, decimal precision loss in currency fields (float `0.1 + 0.2` for money — MUST use integer cents or Decimal types).
- **Unverified type cast**: `as T` in TS without runtime validation guard; data from API/DB/JSON assumed typed but never checked.

Each entry: CRITICAL severity unless provably unreachable path.

---

### Category 2: 🔴 Security / PII / Compliance (CRITICAL or HIGH)

Reuse **harness-compliance** skill categories — but applied to the PR DIFF only (light scan equivalent).

Checks:
1. **Secrets/credentials** hardcoded: Stripe `sk_*`, GitHub PAT, AWS AKIA, private keys, API keys in env vars printed. CRITICAL.
2. **Raw PII logging**: `console.log(email)`, logger with unhashed `phone`. CRITICAL or HIGH depending on context (dev log vs prod persistent log).
3. **SQL injection**: string-concatenated SQL, `.raw()` / `.whereRaw` with no parameterized array. HIGH usually, CRITICAL if user input flows unfiltered.
4. **XSS / SSRF**: `dangerouslySetInnerHTML` without sanitization; user-controlled `fetch(url)` without hostname whitelist. HIGH.
5. **Auth/RLS bypass**: endpoint missing auth guard; server action checking role AFTER the DB write; service_role key used on client. CRITICAL.
6. **Destructive operations + missing guardrails**: DROP TABLE / TRUNCATE without `NODE_ENV !== 'production'` check; `fs.rm(force:true recursive:true)` with user-supplied path.
7. **Dangerous URLs**: new DB URLs pointing to production-looking hosts (`*.rds.amazonaws.com`, `*.supabase.co`, `*.neon.tech`) — flag HIGH, require confirmation.

---

### Category 3: 🟠 Unjustified dependency / blast radius issues (HIGH or MEDIUM)

Checks:
- **New dependency added to package.json/Cargo.toml/requirements.txt/go.mod** AND:
  - It wasn't mentioned in the ticket/scope
  - There's NO justification comment in the PR body
  - A cursory repo search shows a similar helper/function/module already exists
- **PR with >30 files changed** WITHOUT a clear justification in the PR description why this can't be split into 2+ smaller PRs. (Flag as MEDIUM risk — harder to review, higher chance of hidden bugs.)
- **File added outside the module area** that the scope was supposed to touch — scope creep indicator.

---

### Category 4: 🟠 Scope deviation (things PR does that ticket DID NOT ASK FOR) (MEDIUM — blocking per user spec)

How:
1. Take scope description / ticket ACs.
2. For each file changed: classify what that file implements.
3. Compare:
   - **Missing from PR** = ACs not implemented → CRITICAL/HIGH depending on severity
   - **Added to PR but never mentioned** = scope creep → MEDIUM severity, must justify; user explicitly asked us to flag this.
   - Examples:
     - Ticket = "fix login 500" → PR also adds "new forgot password feature" → SCOPE CREEP, flag MEDIUM.
     - Ticket = "add event search" → PR skips the pagination AC mentioned → MISSING, flag HIGH.

---

## 3. NON-goals (we explicitly skip these — do NOT waste tokens / time)

- ❌ Biome / formatting / indentation issues. (That's lint CI.)
- ❌ Naming nitpicks: `myVar` vs `my_variable`, component naming casing. (Unless name is actively misleading to the point of causing bug, which is Category 1.)
- ❌ Test coverage% alone (we check if tests MISS for CRITICAL code but won't demand lines).
- ❌ Documentation README unless it's actively misleading about security/usage.
- ❌ TODO/FIXME comments (unless for auth/security debt).
- ❌ General refactors that don't risk correctness.

---

## 4. Output — Structured Review Report (English for files/code refs, PT for user narrative)

Follow template: `references/REVIEW_REPORT_TEMPLATE.md`

**Header (mode-dependent):**
- Mode A (PR URL): Write a first line `# Review Report — PR #<PR_ID>: <title>`
- Mode B (Worktree Local): Write `# Review Report — LOCAL WORKTREE MODE` then `## Context` with subfields:
  - Worktree path: `<WORKTREE_ROOT>`
  - Current branch: `<BASE_BRANCH_HEURISTIC>`
  - Changed files count: `<changedFiles_count>`
  - Diff stat: `<+additions / -deletions>`
  - Changed files list (table: Status | Path | +/- lines)

For each finding (both modes identical from here):
- Severity: 🔴 CRITICAL / 🟠 HIGH / 🟡 MEDIUM / LOW WARN NON-BLOCKING
- Category: Runtime / Security / Deps / Scope
- File:line
- Snippet (3 lines before + 3 lines after, from patch)
- Why this is a problem (evidence-based — never "I don't like it")
- Actionable fix — specific lines/what should replace
- Optional: suggest code change snippet ONLY if obvious. NEVER rewrite whole file.

Then at the end (both modes, except verdict notes):
- **Verdict**: 🔴 Request changes (≥1 CRITICAL or ≥2 HIGH) / 🟡 Approve with comments (only MEDIUMs/LOWs) / 🟢 Approve
  - **Mode B NOTE**: Verdict labels above refer to "if this were submitted as a PR". Since it's local work-in-progress, interpret as: 🔴 = Fix these before committing/pushing; 🟡 = Fix before merging; 🟢 = Clean.
- **Blocker summary**: numbered list — each CRITICAL/HIGH must be fixed before merge (or before commit+push in Mode B)
- **Non-blocker nice-to-have**: numbered list — MEDIUM/LOW, fix or ignore, user decides

---

## 5. Post-report actions

### Mode A (GitHub PR) — unchanged:
- Write review report TO DISK at:
  `<WORKTREE_ROOT if provided else current-dir>/.trae/review_PR-<ID>_<YYYYMMDD>.md`
  (If no worktree provided by user, write report to chat + offer to save at `.trae/` of user's choice.)
- **DO NOT approve or request changes DIRECTLY on GitHub via `gh pr review`** unless user explicitly asks after seeing the report and saying "suba isso como review oficial". Our first deliverable = the report for the user to review in chat.
- If there are ZERO findings → still write a report saying "No CRITICAL/HIGH issues found; scope matches; dependencies justified." + list what you checked so user trusts the review was actually done.

### Mode B (Local Worktree) — NEW:
- Write review report TO DISK at:
  `<WORKTREE_ROOT>/.trae/review_LOCAL-WORKTREE_<YYYYMMDD>_<HHMMSS>.md`
  (Timestamped because there may be multiple local review passes before code is committed.)
- **DO NOT interact with GitHub at all** in Mode B (no gh commands, no PR creation). Pure local output only.
- Zero findings → still write report with: "No CRITICAL/HIGH issues found in modified files. Scope matches stated goals; dependencies justified." Include the full changed files list + what you checked per category (Runtime/Security/Deps/Scope) so user trusts audit was actually done.
- Optional user convenience at end of chat message:
  - If Mode B, after presenting findings, offer ONE follow-up action:
    - `[Apply fixes locally]` — if user says yes, proceed using harness-developer mindset to fix the CRITICAL/HIGH blockers inside the same worktree (still under scope; don't add features).
    - `[Show just the blocked items condensed]` — for brevity.
    - `[Nothing, thanks]` — stop.
  Don't be pushy. If user just says "ok thanks" → stop.
