---
name: "che-diff-context"
description: "Context builder for diff conversations. TWO MODES: (A) GitHub PR URL — summarizes description + diff + CI checks into a lightweight 'what this PR does' conversation brief. (B) Local Worktree via --worktree <path> — compares to default branch (ask if ambiguous) and splits analysis into already-committed vs to-commit vs untracked with risks. PURPOSE: give you ready talking points to discuss a PR/diff with another developer; NOT a blocking code review (that's che-code-review)."
---

# Che — Diff Context (Conversation Brief Builder)

> **SHARED REFERENCES (CANONICAL — DO NOT DUPLICATE body here):**
> - Security + PII + compliance patterns (if flagged during analysis): `_shared_checklists/SECURITY_PII_COMMON.md`
> - GitHub CLI gh auth + PR metadata commands: `_shared_checklists/GITHUB_CLI_COMMON.md`
> - Worktree Session Binding rules (one session = one worktree, ask on doubt): engineering-contracts §19
> - Output shape rules (concise 4 sections + diagonal readability): engineering-contracts §18

## 🆚 Clear boundary from che-code-review (DO NOT overlap)

| Concern | `che-code-review` | This skill `che-diff-context` |
|---|---|---|
| **Goal** | Block production breaks. Verdict: 🔴/🟡/🟢. | Give user **conversation context** so they can talk to someone about this diff. No verdict, no approve/request-changes. |
| **Scope** | ONLY CRITICAL + HIGH blocking issues (Runtime / Security / Deps / Scope deviation). | EVERYTHING the user needs to understand intent + changes + CI state + talking points. Mild concerns are OK as "things to bring up". |
| **Output** | Review report with numbered blocking issues. | Lightweight brief: What / Main changes / CI / Attention points. Narrative structure for dialogue. |
| **Severity tone** | Bold red blockers. Polite but firm. | Neutral, descriptive. "Potential risk worth discussing" vs "this is broken." |
| **Call to action** | "Fix X before merge" or "Approve". | "3 things I'd ask about in review: A, B, C." |

**Rule:** User says "review this / approval / blocking issues" → use `che-code-review`. User says "context / understand what was done / prepare to talk about this diff" → use THIS skill. Never mix.

---

## 0. Preconditions — Two modes (PICK EXACTLY ONE)

### How to decide which mode
- **If user provides a GitHub PR URL** (starts with `https://github.com/` or `gh/.../pull/`) → **FORCE Mode A (PR Context)**. Worktree optional.
- **If user passes `--worktree <path>` (or equivalent explicit worktree indicator) AND NO GitHub PR URL** → **FORCE Mode B (Local Worktree vs Default Branch)**.

---

### Mode A — GitHub PR URL (Conversation Brief)

#### A.0 Preflight

1. **`gh` CLI authenticated:** Run `gh auth status` silently. If not → guide user to `gh auth login` then stop.
2. **PR URL reachable:** Validate URL format + run a tiny `gh pr view <url> --json number,title` to confirm it exists. If 404 / 403 → stop and report.
3. **Worktree binding optional + 🔴 STORAGE PREFLIGHT (BEFORE first write):** If user also gave `--worktree <path>`, write/read session binding per §19 (ask if mismatch). **In ANY mode (A or B), BEFORE saving the first file to disk, run:**
   ```bash
   # Resolve the `che` CLI — it owns the 5-tier Che-home cascade (CHE_HOME → HARNESS_HOME
   # → ~/.che-ai → legacy ~/.trae iff CHE_RULES.md exists → ~/.che-ai fallback).
   command -v che >/dev/null 2>&1 || { echo "❌ FATAL: 'che' CLI not found on PATH. Zero writes without storage boundary. exit 98"; exit 98; }
   SESSION_ID="${CHE_SESSION_ID:-${HARNESS_SESSION_ID:-fallback-diffctx-session}}"
   if [ -n "${WORKTREE_ROOT:-}" ] && [ -d "$WORKTREE_ROOT" ]; then
     eval "$(che compute_paths "$WORKTREE_ROOT" "$SESSION_ID" --cwd "$PWD")"
     che ensure_dirs "$WORKTREE_ROOT" "$SESSION_ID" --cwd "$PWD"
   fi
   # AFTER this: use ONLY `che output_path "diff_context" ...` to build paths.
   ```
   NEVER use `./reports/` or paths inside the worktree. §20 MORATORIUM.

#### A.1 Context collection (3 sources)

##### A.1.1 PR description + metadata
Run:
```bash
gh pr view <PR_URL> --json \
  number,title,body,author,state,isDraft,baseRefName,headRefName,additions,deletions,changedFiles,commits,labels,reviewDecision,mergeable,createdAt,updatedAt
```
Extract fields:
- **Title + number**
- **Body summary** (1–3 sentences max; if body > 30 lines → pick TL;DR header or first paragraph only)
- **Author, Draft/Ready, Base → Head branch**
- **Diff stats** (lines + files + commits count)
- **Labels / linked issues** if any

##### A.1.2 Diff changes (main code areas touched)
Run:
```bash
gh pr diff <PR_URL> --name-only
```
Build:
- **Top 5–8 most meaningful files** sorted by additions+deletions. Group by folder/module (e.g., `packages/db/*`, `packages/platform/app/api/*`).
- **One-liner per group:** e.g. "`packages/db` — 2 new entities + 1 migration".
- **Flag obvious big groups:** if a single group has >40% of diff → highlight as "main blast radius".

##### A.1.3 CI checks status
Run:
```bash
gh pr checks <PR_URL>
```
Build 1-line summary buckets:
- **Passing count / Total count**, plus names of any **FAILED** checks.
- For failed checks: 1-sentence log headline (from first 3 lines of run log if possible via `gh run view` on failed).
- Note "Pending" count separately.

#### A.2 Conversation Brief Canonical Output Sections (exactly 5 — match user's goal)

The output saved to disk AND presented to user uses THESE sections in THIS order. Follow §18 diagonal formatting (headings + bullets + bold key words).

```markdown
# 📋 Diff Context — PR #<N> — <Title>

**Mode:** GitHub PR URL | **Worktree:** <path or "none (GitHub-only)"> | **Generated at:** <ISO ts>

---

## 1. 🧭 What this PR implements (high-level context)
1–3 clear sentences. Answers: "What problem does it solve? What is the new behavior?"
- Use title + body summary.
- If body has Acceptance Criteria → copy max 5 core AC bullets.
- DO NOT reproduce entire body. Trim.

## 2. 🧩 Main change areas (blast radius per module)
Max 6–8 bullets. Each bullet = 1 module/group + 1 verb + what changed.
E.g.:
• **packages/db — entities + migration**: `TicketRefund` entity + SQL migration adds `refund_status` enum.
• **packages/platform/api/refunds — endpoint**: `POST /api/events/:id/refunds` + Stripe refund call.

Section end → 1 summary line: **Total:** X files / +Y lines / -Z lines / W commits.

## 3. ✅ CI Checks Status
• **Global:** <passing/has failures/pending> — <M> passed / <N> failed / <P> pending of <TOTAL>.
• **Failed checks (if any):**
  - <Check 1 name>: <1 line cause, e.g. "build platform step 42 TypeScript type error: ...">
  - <Check 2 name>: ...
• **GitHub Review Decision (if any):** reviewDecision field.

## 4. 🔴 Risks / Broken things I see (slightly critical)
Space for clear problems but NO BLOCKING verdict (different from code-review). Max 3 bullets.
- If none: say "No obvious risks in analyzed diff."
- Typical examples: "New endpoint has no explicit permission check (verify if inherited from parent middleware)"; "Migration DROP without documented rollback"; "Secret key appeared 1 line — looks like dummy placeholder, confirm".

## 5. 💬 3 Attention Points FOR YOU TO DISCUSS about this PR
MAXIMUM 3 items. 1 sentence each. These are your topics to bring up in call/comment.
• Point 1: Question about architecture / approach
• Point 2: Test coverage or missing edge cases
• Point 3: Alignment with PR body ACs / ticket
```

#### A.3 Save + delivery
**Construct path ONLY via helper (preflight already ran in A.0 item 3):**
```bash
# Mode A = PR URL → related_id = pr-<N>; type = diff_context; scope = session (ephemeral)
DIFFCTX_PATH="$(che output_path "diff_context" "diff-context" "pr-${PR_ID}" "session" "md")"
```
Example result: `$CHE_SESSION_DIR/diff_contexts/pr-382/20260902-103000-diff-context.md`
→ Fallback without binding is handled by helper (lands in `$CHE_HOME/outputs/fallback-session/...` never worktree).
→ UTC timestamp prefix ensures ordering if run multiple times on same PR.

Delivery to chat follows §18 shape: **📍 Status / 🧩 Summary / 🔗 Refs / ❓ Deep-dive**.
Never dump full 5-section report into chat verbatim unless user says "show everything". Chat summary = condensed 3 bullets from each of sections 1/2/3 + warning if section 4 > 0 items. Offer: "Full report saved to disk or show full text here?".

---

### Mode B — Local Worktree — Diff vs Default Branch

> **Goal same as Mode A: conversation context.** Only difference: source = LOCAL WORKTREE, and we split into 3 temporal buckets vs PR's single diff.

#### B.0 Worktree preflight (engineering-contracts §19, NON-NEGOTIABLE)

Run BEFORE any git command.

1. **`WORKTREE_ROOT` = absolute path from `--worktree` flag.**
2. **Valid git worktree check:** `cd <WORKTREE_ROOT> && git rev-parse --is-inside-work-tree 2>/dev/null` → true. If not → stop.
3. **Session binding file read:** Read `$CHE_SESSION_DIR/binding.md` if exists (via contract).
   - If exists and `WORKTREE_ROOT` entry ≠ provided path → BLOCK. Ask user: "Session binding says X but you asked Y. Proceed with Y anyway? (A = Y override; B = Switch back to X; C = Cancel)". Never silent override.
   - If binding file missing → follow §19 canonical 2-LEVEL flow (global registry Level 1 + Level 2 in session dir). Ask user to confirm worktree once.

#### B.1 Resolve BASE BRANCH (if in doubt = ask)

Goal: find branch to compare AGAINST. This is the "default comparison branch" user would open a PR against.

1. **Try auto-detect first:**
   - Fetch remote default branch: `cd <WORKTREE_ROOT> && gh repo view --json defaultBranchRef --jq .defaultBranchRef.name 2>/dev/null`. If string like `main`/`master`/`dev` → candidate 1.
   - Local branches list sorted by most recent: `git branch -a --sort=-committerdate | head -20`
   - Heuristic: candidate 2 = remote `origin/dev`, `origin/develop`, `origin/main` commonly used.
2. **Ambiguity rule (§19 doubt = ask):**
   - If ≥2 equally-valid candidates (e.g., `origin/dev` AND `origin/main` both exist and recent) → **STOP. Ask user directly.**
   - Ask format (AskUserQuestion 2 choices max + other):
     > Compare against which base branch?
     > A) `origin/dev` (most recent, dev staging)
     > B) `origin/main` (production)
     > (other / type name)
3. **Once BASE_BRANCH resolved:** Record `BASE_BRANCH_REF = origin/<name>` (remote preferred to compare worktree vs actual upstream base, not stale local copy).

#### B.2 Context collection (4 buckets = key difference from Mode A)

Run all git commands inside `<WORKTREE_ROOT>`.

##### B.2.1 Bucket 1 — 🟢 Already Committed (on this branch, NOT YET on BASE_BRANCH)
This = things that WILL be in a PR if opened now.
```bash
# Commit list vs base
BASE=<BASE_BRANCH_REF>
git log --oneline --decorate ${BASE}..HEAD
# Diff stat
git diff --stat ${BASE}..HEAD
# Diff names-only grouped
git diff --name-only ${BASE}..HEAD
```
Extract:
- Top 3–5 most recent commit messages (oneliner).
- Top 5–8 file groups as in Mode A.2.
- Commits count + file count.

##### B.2.2 Bucket 2 — 🟡 To Commit (STAGED + UNSTAGED tracked changes)
This = local work-in-progress NOT in any commit on this branch yet.
```bash
git status --short  # filter M/A/D/R + space or M (not ??)
# staged only
git diff --cached --stat
git diff --cached --name-only
# unstaged only (tracked)
git diff --stat
git diff --name-only
```
Extract:
- Counts: staged N files / unstaged M tracked files.
- Key modified files (list 5–8).
- Note: "Large unstaged change = risk of accidentally shipping half-baked work".

##### B.2.3 Bucket 3 — ⚪ Untracked (?? files NOT yet added)
```bash
git ls-files --others --exclude-standard   # respect .gitignore
```
Rules:
- Skip: `node_modules/`, `.next/`, `dist/`, build artifacts.
- If ≤5 untracked → list all by path.
- If >5 → list first 5 + "and <K> more".
- Flag any **untracked `.env*` or secret-looking files** immediately (Security quick flag).

##### B.2.4 Bucket 4 — 🔧 Current branch metadata
- Current branch: `git branch --show-current`
- HEAD commit short SHA
- Worktree clean/dirty boolean
- Optional stash count: `git stash list | wc -l`

#### B.3 Conversation Brief Canonical Output (Mode B)

Same rule as Mode A: 5 fixed sections, §18 diagonal shape. Buckets 1/2/3 replace PR diff.

```markdown
# 📋 Diff Context — Local Worktree vs <BASE_BRANCH_REF>

**Mode:** Local Worktree | **Path:** <WORKTREE_ROOT> | **Current Branch:** <BRANCH> | **Generated at:** <ISO ts>
**Clean/Dirty:** <clean|dirty> | **Stashes:** <N> | **Commits ahead of base:** <W>

---

## 1. 🧭 What is being developed here (high-level context)
1–3 sentences. Based on last commit messages + main files.
- Combine top 3 commit oneliners into short narrative.
- If commits "WIP" / vague → say "Context in commit titles not clear; focusing on sections 2.1–2.3 below".

## 2. 🧩 Main changes by stage (for discussion)

### 2.1 🟢 Already Committed (W commits / X files / +Y / -Z)
Max 5 bullets:
• Main recent commits (3–5 oneliner).
• Main modules/areas affected (as in Mode A section 2).
• 1 line: general state of this part (e.g. "Refund pipeline complete in commits, migration refactor half done").

### 2.2 🟡 To Commit (staged N, unstaged M tracked files)
Max 5 bullets:
• Main files with staged changes.
• Main unstaged files (WIP).
• Flag: if any migration/security file has UNSTAGED changes.
• Summary line: % of work appearing as WIP vs ready.

### 2.3 ⚪ Untracked / New files not yet added (K)
• List 5 most important + path.
• Flag env/secrets if present.
• "K > 5" warning.

## 3. ✅ Local build/lint status hints (if possible, 1 line each)
If easy via known pipeline (Nx/pnpm workspace):
• DO NOT run full lint+build+tests (overkill). Quick check only: run 1 package typecheck if ≤ 10s.
• If none run → say: "No local checks executed; run `corepack pnpm nx run <pkg>:typecheck` to confirm types in changed area."

## 4. 🔴 Highlighted Problems / Risks (before formal review)
Max 3 bullets. Something clearly wrong OR risky in current state.
Typical examples:
• "Migration with ALTER TABLE DROP COLUMN without rollback comment / down migration"
• ".env.local is untracked (contains likely real keys — **careful** if this worktree is shared)"
• "File `refunds.ts` has ~400 lines changed unstaged — risk of half-done work if opening PR now".
None = "No obvious immediate risks".

## 5. 💬 3 Attention Points TO DISCUSS / PREPARE FOR
MAXIMUM 3, 1 sentence each:
• 1 point on current vs desired scope (still missing? Which pieces)
• 1 point on committing order (what to commit first / leave WIP)
• 1 point on opening PR now vs waiting for more commits
```

#### B.4 Save + delivery
**Construct path ONLY via helper (preflight already ran in A.0 item 3, reuse here — if not run yet, run NOW before write):**
```bash
# If A.0 item 3 preflight NOT run (user jumped to Mode B), GUARANTEE here:
if [ -z "${CHE_SESSION_DIR:-}" ]; then
  command -v che >/dev/null 2>&1 || { echo "❌ FATAL: 'che' CLI not found on PATH. Zero writes without storage boundary. exit 98"; exit 98; }
  SESSION_ID="${CHE_SESSION_ID:-${HARNESS_SESSION_ID:-fallback-diffctx-local-session}}"
  if [ -n "${WORKTREE_ROOT:-}" ] && [ -d "$WORKTREE_ROOT" ]; then
    eval "$(che compute_paths "$WORKTREE_ROOT" "$SESSION_ID" --cwd "$PWD")"
    che ensure_dirs "$WORKTREE_ROOT" "$SESSION_ID" --cwd "$PWD"
  fi
fi
# Mode B = Local Worktree → related_id = worktree-<slug>
WT_SLUG="$(basename "${WORKTREE_ROOT%/}")"
DIFFCTX_LOCAL_PATH="$(che output_path "diff_context" "diff-context-local" "worktree-${WT_SLUG}" "session" "md")"
```
Example result: `$CHE_SESSION_DIR/diff_contexts/worktree-feat-FLO-714--X/20260902-110000-diff-context-local.md`
→ Multiple local passes ordered by UTC timestamp automatically.

Chat delivery follows §18 shape (condensed).

---

## General rules for BOTH modes

1. **No verdict.** Never "Approve / Request Changes". That is **only** `che-code-review`.
2. **Report ≤250 lines max.** If diff huge → pick top changes; don't enumerate every file.
3. **§18 response verbosity budget active for chat delivery.** Chat summary 250–500w, 4 sections, 3 bullets max. Full report = saved to disk.
4. **§19 worktree binding active on any mode touching disk writes.** Always read binding file if worktree path known.
5. **NEVER invent PR body / commit intent.** If titles/vague → explicitly say "context from authors not clear, recommend asking".
6. **PII / secrets scanning (light):** Quick grep (same as compliance patterns) while collecting diffs — if raw key/token shows up, **flag immediately in section 4 regardless of content.**
