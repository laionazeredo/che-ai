---
name: "harness-pr-comments"
description: "Scans all comments on a GitHub PR, classifies them (human vs bot / valid vs invalid / actionable vs nitpick), produces a structured triage report, and prepares: (a) a numbered implementation plan for valid actionable comments, (b) pre-written English responses for comments we should reject/ignore. Invoke when user passes a PR URL and asks to process review comments, or when /harness-pr-comments is called."
---

# Harness — PR Comments Triage & Response Drafts

> **SHARED REFERENCES (CANONICAL — NÃO DUPLICAR corpo aqui):**
> - GitHub CLI gh auth + pull/post comments commands: `_shared_checklists/GITHUB_CLI_COMMON.md`
> - Security/PII triage for review comments about compliance: `_shared_checklists/SECURITY_PII_COMMON.md`

Given a GitHub PR URL, this skill:
1. Pulls ALL comments (issue-level + review-level + individual file review comments) via `gh`.
2. Classifies and groups.
3. Produces a triage report: what to IMPLEMENT, what to RESPOND and reject, what to mark as resolved without action.

**NEVER actually posts comments to GitHub UNLESS user explicitly says "suba essas respostas". First deliver the triage + plan + draft responses to the user chat for approval.**

---

## 0. Preconditions

1. **PR URL** from user. If missing → ASK.
2. **`gh auth status` OK.** If not → guide user and stop.
3. Worktree path optional: if provided, we can actually implement the valid ones later. If not, triage and drafts only.

---

## 1. Gather ALL PR comments

Use `gh` CLI (not browser):

```bash
# Issue-level comments (PR body replies, general comments)
gh pr view <PR_URL> --json comments,number > /tmp/issue-comments.json

# Review-level: every review (APPROVED / CHANGES_REQUESTED / COMMENTED) + per-file comments inline
gh pr view <PR_URL> --json reviews > /tmp/reviews.json
# Reviews include .comments[] on each review (in-file line comments)
```

Flatten and de-duplicate into one list: `ALL_COMMENTS[]`.

For each comment record:
```
id:
author_username:
author_association: OWNER / MEMBER / COLLABORATOR / CONTRIBUTOR / FIRST_TIME_CONTRIBUTOR / NONE
body_text: raw markdown / text
is_bot: true/false (check username ends with [bot], or known bot list: dependabot[bot], renovate[bot], codecov[bot], github-actions[bot], lintr[bot], snyk-bot, vercel[bot], deploy-preview, sonarcloud...)
in_reply_to_comment_id: null or parent id
file_path: null (issue-level) OR path (inline review)
line_number: null or line number
created_at: ISO
resolved? (optional: look at review comments API for resolved flag)
```

---

## 2. Classify EACH comment into categories

### 2.1 Author kind → HUMAN vs BOT vs SYSTEM

- **BOT / CI**: if username matches known bot list or `author_association=NONE + username contains bot`.
  Examples: codecov comment, dependabot merge conflict note, lint warning line note, vercel preview URL.
- **SYSTEM / meta**: "This PR was edited by ...", merge conflict banner, auto-generated release notes.
- **HUMAN**: everything else.

### 2.2 Content classification

For BOT comments → auto-classify:
| Pattern | Classification |
|---|---|
| Codecov report: "Coverage decreased by 0.3%" | BOT_COVERAGE (INFO, usually non-actionable unless >3% drop) |
| Lint bot inline line note | BOT_LINT_WARNING — cross-check with latest CI run; if CI clean, outdated, mark resolved |
| Dependabot alerts / vuln notice | BOT_VULN — HIGH priority, must act |
| Renovate version bump description | BOT_DEPS — meta |
| Vercel preview URL deployment | BOT_PREVIEW — link only, no action needed unless link broken |
| SonarCloud quality gate fail | BOT_SONAR — cross-check findings |
| Any bot with "This branch has conflicts that must be resolved" | BOT_MERGE_CONFLICT — HIGH, PR block, must fix. |

For HUMAN comments → classify content:

| Sub-type | Signals | Actionable? |
|---|---|---|
| **CORRECTNESS_REQUEST**: actual bug / logic issue | Phrases: "This crashes when X", "this should return Y when Z"; includes example input/output; refers to runtime behavior | ✅ YES, HIGH priority |
| **SECURITY_REQUEST**: PII / injection / auth issue | Keywords: security, PII, log this email, SQL string concat, no auth check | ✅ YES, CRITICAL priority |
| **ARCHITECTURE_REQUEST**: cross-module concern | "We should move this to X layer instead", "this couples A+B which is bad" | ✅ YES, MEDIUM priority — only if reviewer gives rationale; vague "this is bad architecture" = DISCUSSION |
| **SCOPE_CREEP_WARNING**: "this should NOT be in this PR" | Reviewer points out extra code unrelated to ticket | ✅ YES, per user spec: scope deviation must be flagged |
| **QUESTION**: reviewer doesn't understand, asks why | "Why did you use X instead of Y?", ends with `?` | ✅ RESPONSE needed, NO code change required |
| **NIT / STYLE_PREFERENCE**: Biome / format / naming preference | "Rename to snake_case pls", "extra blank line" | ⚠️ LOW priority. Usually response "Done" if easy; otherwise repo convention decides. |
| **PRAISE / LGTM / APPROVAL_META**: "Looks good", "nice work", "LGTM!" | | ❌ No action |
| **DISCUSSION / OPINION**: debatable, no clear right/wrong | "IMO we should use zod here not manual" (when repo already uses manual guards) | ❌ Discussion only. Respond once explaining rationale; don't change unless maintainer overrules OR you agree it's a good idea anyway |
| **OUTDATED**: comment on line that was already changed / no longer applies | | ❌ Mark resolved with "Fixed in <commit sha>" or without response |
| **DUPLICATE**: same exact point already raised by another comment | | ❌ Ignore after confirming duplicate |

---

## 3. Triage Report Structure

Write file: `$HARNESS_WORKSPACE_SHARED/pr_comments/pr-<ID>_<YYYYMMDD>.md`
(Resolve via `source $HOME/.trae/contracts/harness_sessions_contract.sh && harness_compute_paths $WORKTREE_ROOT $SESSION_ID && harness_ensure_session_dirs $WORKTREE_ROOT` first; NEVER create `<worktree>/.trae/` dirs.)

### Summary table

| Bucket | Count |
|---|---|
| BOT comments (total) | `N` |
|   BOT_MERGE_CONFLICT (action required) | `N` |
|   BOT_VULN (action required) | `N` |
|   BOT_COVERAGE / LINT_WARNING / PREVIEW / DEPS / META (no action) | `N` |
| HUMAN comments (total) | `N` |
|   ✅ TO IMPLEMENT — Code change required | `N` |
|   ✏️ TO RESPOND — No code change, draft reply needed | `N` |
|   ❌ OUTDATED / DUPLICATE — Resolve silently | `N` |
|   💬 PRAISE / LGTM / APPROVAL_META — Ignore | `N` |
|   ⚠️ NIT — Optional, decide per user | `N` |
|   🗣️ DISCUSSION / OPINION — User decides | `N` |

---

### Section 1: ✅ TO IMPLEMENT (sorted by priority: CRITICAL → HIGH → MEDIUM → LOW)

Each entry:
```
## I-1 <severity> — <short description>

Reviewer: @username (role: COLLABORATOR)
File:line: path/to/file.ts:42
Original comment body:
> <quoted markdown>

Rationale for implementation:
<1 sentence: this is a real bug / security issue / scope mismatch → must act>

Proposed code change plan:
- File 1: change lines XX-YY → replace `<old>` with `<new>`
- File 2: ...
- Tests: add / modify spec at `<path>` to cover this fix

Estimated blast radius: N files (≤ 10 or flag for user re-evaluation)
Estimated effort: XS / S / M / L
```

### Section 2: ✏️ TO RESPOND — Human comments, no code change

Each entry:
```
## R-1 — <short title of what comment was>

Reviewer: @<username>
Context: <issue-level or in-file:path:line>
Original comment:
> <quoted>

### Decision: NOT IMPLEMENTING — Respond only.

Rationale (1 line):
<why we are NOT making the code change. E.g.: "Repo convention uses manual guards everywhere already; moving to zod here is inconsistent + out of scope for this ticket. We can open follow-up for migration.">

### Draft response (ENGLISH, ready to paste — professional, constructive, never argumentative):

Thanks for raising this, @<username>! 🙏

<explain why we're not changing, short, polite>
- Concretely: the current approach matches the repo convention at <reference to 1-2 existing files doing the same pattern>.
- I'll note this down as a follow-up idea for a separate refactor PR (ticket: <link if available>), so we don't lose it.
- Let me know if you still feel strongly and we can re-discuss! 👍
```

### Section 3: 💬 DISCUSSION — User decides (we draft BOTH sides)

```
## D-1

Reviewer: @
Comment: "IMO use zod instead."

If USER wants to IMPLEMENT → Implementation plan same format as Section 1.
If USER wants to DECLINE → Draft response similar to Section 2.
Decision: PENDING USER CHOICE.
```

### Section 4: NITs — quick / optional

```
## N-1 — "rename var to snake_case"

Action: DONE via trivial edit (≤ 5 min effort). We'll include in same commit batch.
OR
Action: DECLINED + response (see Section 2 style).
```

### Section 5: OUTDATED / DUPLICATE / RESOLVED SILENTLY

Numbered list with IDs and 1-line: "Resolved without posting a reply."

---

## 4. Proposed aggregated implementation plan (if user says "proceed with implement")

Aggregate all Section 1 items into logical batches (atomic commits):

```
Aggregated plan:

Batch 1 — Commit: fix(security): patch email log PII leak in order flow
  • I-1 (CRITICAL) — path/to/log
  • Tests: update log assertion specs

Batch 2 — Commit: fix(correctness): early return when profile is null
  • I-2 (HIGH) — renderPhone function
  • Tests: add null profile test case

Batch 3 — Commit: chore(scope): remove password reset feature added by mistake
  • I-3 (MEDIUM scope creep) — delete PasswordReset.vue + references

Estimated total new commits: 3
Estimated total files touched: 6 (≤ 10 ✅)
```

---

## 5. Hard stops / rules

- **Never write a response that sounds aggressive / dismissive.** Always: thank → explain rationale → offer follow-up / alternative path.
- **Never auto-decide ARCHITECTURE_REQUEST or DISCUSSION when reviewer is a repo OWNER/MEMBER.** Flag to user: "Este reviewer é owner/mantenedor. Sugiro implementar a menos que você discorde fortemente."
- **Never auto-post replies to GitHub.** Only do so when user explicitly types: "suba essas respostas" or similar, and AFTER user approves the full triage report + plan + response drafts.
- If any comment says "Merge conflicts" / "This branch is out-of-date with base" — classify as BOT_MERGE_CONFLICT → HIGH priority, must resolve as part of Section 1 before anything else.
