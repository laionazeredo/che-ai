# REVIEW REPORT TEMPLATE (for PRs)

> Used by `harness-code-review` when it finishes analyzing a GitHub PR.
> Output language: ENGLISH for the structured report.
> User-facing summary (printed to chat) is in PORTUGUESE per the global rules.

---

# 🔍 Code Review Report — PR #<PR_NUMBER>

- **PR:** `owner/repo#<N>` — `<PR title>`
- **URL:** `<link>`
- **Base:** `<BASE_BRANCH>` → **Head:** `<HEAD_BRANCH>`
- **Diff stats:** `+N additions` / `-M deletions` / `F files changed`
- **Author:** @<github-username>
- **Scope reference:** `<ticket URL or "inline description provided">`
- **Review date:** `<ISO datetime>`

---

## Executive Verdict

| Verdict (choose one) | Meaning |
|---|---|
| 🔴 **REQUEST CHANGES** | Must fix blocking issues before merge. |
| 🟡 **APPROVE WITH COMMENTS** | Can merge AFTER user decides on non-blocking; nothing breaks. |
| 🟢 **APPROVE** | No blocking issues detected. LGTM. |

### Blocker tally
| Severity | Count |
|---|---|
| 🔴 CRITICAL | `N` |
| 🟠 HIGH | `N` |
| 🟡 MEDIUM (non-blocking unless scope policy) | `N` |
| 🔵 LOW | `N` |

---

## Findings

### #F-1 🔴 CRITICAL — Category: Runtime — `path/to/file.ts:<line>`

**Why it matters:**
- (Short explanation. Evidence-based — not subjective.)
- Null dereference of `user.profile.phone` when `profile` is `null`. Happens in `/profile` route for new users who never filled profile (confirmed by types `profile?: Profile | null`).

**Diff snippet:**
```diff
@@ -40,3 +40,5 @@ function renderPhone(user) {
+    // ...
+    return user.profile.phone
 }
```

**Recommended fix:**
- Add optional chaining + early return / null guard BEFORE accessing `.phone`.
```typescript
if (!user.profile || !user.profile.phone) return "—";
return user.profile.phone;
```

---

### #F-2 🟠 HIGH — Category: Security / PII — `path/to/server.ts:<line>`

**Why it matters:**
- Raw email address being logged with info level. `NOTIFICATION_PII_HASH_SECRET` exists and repo convention says use `hashPII(email)` for correlation.

**Recommended fix:**
```diff
- logger.info({ email: order.customerEmail }, "Order created")
+ logger.info({ customerEmailHash: hashPII(order.customerEmail) }, "Order created")
```

---

### #F-3 🟡 MEDIUM — Category: Scope deviation — Adding `PasswordReset.vue`

**Why it matters:**
- Scope reference (ticket FLO-123): "fix login 500 error." PR BODY does not mention password reset. This feature was not asked for or documented.
- Recommend splitting into a separate PR so reviewers can actually review the security implications of a password reset flow independently.

**Action for user:**
- Either remove from this PR + open separate PR, OR update the ticket scope and add security review checklist.

---

### #F-4 🔵 LOW — Category: Dependencies — `package.json`

**Why it matters (note: non-blocking):**
- Added `date-fns@3.6.0`. Quick check: repo already has `dayjs` installed and used in 22 places. 95% of `date-fns` usages added are achievable with existing `dayjs` API. Not a blocker because it's small, but worth noting for long-term bundle size / de-duplication.

**Action:**
- Optional: Replace with dayjs where possible. OK to leave if user wants the new API.

---

## Coverage of Review (transparency — what we checked)

User should trust we actually ran the full process:

| Category framework item | Checked? |
|---|---|
| 1. Runtime breakage / silent incorrect behavior | ✅ Yes — diff all files line-by-line |
| 2. Security / PII / Compliance (per-task LIGHT level patterns) | ✅ Yes |
| 3. Unjustified new deps / large PR scope | ✅ Yes — 30+ file warning threshold |
| 4. Scope deviation vs ticket / description | ✅ Yes — ACs mapped to changed files |
| Non-goals (style / formatting / naming / coverage %) | ⚠️ Skipped intentionally — that's CI/lint job |

---

## Final user-facing recommendation

**(Written in Portuguese in the actual chat delivery; this template records what was checked.)**

Blocking:
1. Fix F-1 + F-2 before merge.
2. Decide on F-3: scope creep (remove or justify).

Non-blocking nice-to-haves:
- F-4 (deps) — up to you.

After fixes: re-run a short follow-up review, then OK to move to /harness-ship or merge.
