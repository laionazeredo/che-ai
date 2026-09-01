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

## Context Bootstrap Evidence (TRANSPARÊNCIA OBRIGATÓRIA — what files we actually read BEFORE reviewing the diff)

User must be able to verify that the review was context-aware (not superficial diff-only eyeballing). Fill this section IN EVERY REPORT. If a file says "(N/A — doesn't exist in repo)" it still counts as checked; if blank = review is invalid.

| Bootstrap item (§1.5 framework) | Files actually read / checked |
|---|---|
| R1 Root AGENTS.md | `AGENTS.md` — read L1-L85 (router of context) |
| R2 Root CLAUDE.md | `CLAUDE.md` — structure, packages, RLS migration rules |
| R3 Root README.md | |
| R4 docs/plan.md | |
| R5 docs/decisions.md or docs/adr/*.md (last 5) | |
| R6 graphify-out/GRAPH_REPORT.md | (N/A or path) |
| `.claude/rules/*.md` ALL (or `.agents/rules/`) | list each file read: `security.md`, `architecture.md`, `data-layer.md`, `db.md`, `react.md`, `uk-market.md`, `db-caching.md`, `workflow.md`, `tooling.md` |
| Package AGENTS.md (affected areas) | `packages/platform/AGENTS.md`, `packages/db/AGENTS.md`, `packages/notification/AGENTS.md` |
| Package CLAUDE.md (affected areas) | `packages/platform/CLAUDE.md`, `packages/db/CLAUDE.md` |
| Relevant docs/*.md area files | `docs/platform.md`, `docs/packages.md`, `docs/decisions.md` |
| Local project review skill (if exists) | `.claude/skills/flockr-review/SKILL.md` read fully; 9 checklist categories absorbed |
| Cross-file pipeline reads (MANDATORY if diff matches keywords): <br> — Webhook route allowlist <br> — ALL PSP/Connect charge methods in the package | `app/api/webhooks/stripe/route.ts:7-16` (allowlist read) <br> `StripeClient.ts:285-313` (createPaymentIntent) + `RefundService.ts:~450` (createRefund) read |

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

| Category framework item | Checked? | Evidence from bootstrap |
|---|---|---|
| §1.5 Project Context Bootstrap (R1-R6 + Rules + Affected Packages + Local Skill + Cross-file pipelines) | ✅ Yes — see "Context Bootstrap Evidence" table above | |
| 0. Cross-File Pipeline Integrity (0.1 webhook allowlist / 0.2 3-pass Connect charge-model audit / 0.3 tx+locks overlap / 0.4 fire-and-forget Vercel) | ✅ Yes | Files read: `route.ts` allowlist, `StripeClient.ts` PI params 3-pass check, `RefundService.ts` tx span, setImmediate email paths |
| 1. Runtime breakage / silent incorrect behavior + Crash-safety PROCESSING row + substring vs error.code + circular imports + index drift + idempotency null-cast | ✅ Yes — diff all files line-by-line | |
| 2. Security / PII / Compliance (LIGHT level + **per-procedure READ/WRITE split** authz audit 2.8-2.10 — cookie org check + assertCan cache threading + authz BEFORE writes) | ✅ Yes | Each procedure audit: `trpc.ts:46-49`, `context.ts:51` + `bookingRouter` 3 procedures scanned SEPARATELY |
| 3. Architecture layering / Repo boundary **(per-procedure direct repo instantiation check)** + **Migration Hygiene (timestamps fabricated/intra-branch patch/RLS TO PUBLIC defaults)** + Entity dupe + deps scope | ✅ Yes | Router business logic + direct repo instantiation scanned per procedure; 5 migration files scanned for fabricated timestamps/intra-branch enum patch |
| 4. Scope deviation / **UI demo 5-pass scan** (fake latency + random fail + discarded idempotencyKey + toast no API call + demo data imports) / test naming rules / 4.8 route-level test gaps | ✅ Yes — ACs mapped to changed files | RefundBookingAction.tsx 5-pass demo check applied; test behavioral naming rules validated |
| Non-goals (style / formatting / naming / coverage %) | ⚠️ Skipped intentionally — that's CI/lint job | |

---

## Final user-facing recommendation

**(Written in Portuguese in the actual chat delivery; this template records what was checked.)**

Blocking:
1. Fix F-1 + F-2 before merge.
2. Decide on F-3: scope creep (remove or justify).

Non-blocking nice-to-haves:
- F-4 (deps) — up to you.

After fixes: re-run a short follow-up review, then OK to move to /harness-ship or merge.
