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
| Severity | Count | Notes |
|---|---|---|
| 🔴 CRITICAL | `N` | Category 1 Runtime breakage / Category 2 Security PII |
| 🟠 HIGH — TOTAL (soma das linhas abaixo) | `N` | **Blocking threshold = this line; ≤2 HIGH = auto-fix per ship gate §0.9.2** |
| 🟠 · Category 1 Runtime / Crash-safety HIGH | `N` | Subcount |
| 🟠 · Category 2 Security / PII / Authz HIGH | `N` | Subcount |
| 🟠 · Category 3 Architecture / Migration HIGH | `N` | Subcount |
| 🟠 · Category 4 Scope / Demo leak HIGH | `N` | Subcount |
| 🟠 · Category 5 Lean / Overengineering HIGH | `N` | Subcount (future) |
| 🟠 · Category 6 Logging / Observability HIGH | `N` | Subcount (future) |
| 🟠 · **Category 7 Testing Gaps HIGH (G7.1 / G7.2)** | `N` | New — 20+ln src no test / new API-UI without integ or Playwright |
| 🟠 · **Category 8 UI Selector Hygiene HIGH (G8.1 / G8.2)** | `N` | New — interactive UI fragility or fragile test selectors |
| 🟡 MEDIUM (non-blocking unless scope policy) | `N` | Includes G7.3, G8.3 |
| 🔵 LOW | `N` | Includes G7.4, G8.4 |

---

## 🎯 Existing Review Context (from PR comments loaded via gh CLI — Step 0.5 mandatory)

> User must see that existing human review was absorbed into context BEFORE new findings are emitted. Avoid duplicate reviewer work.

| Item | Value |
|---|---|
| **PR review state** | `<N> APPROVED · <M> CHANGES_REQUESTED (authors: @user1, @user2) · <K> COMMENTED` |
| **Inline review threads (hunks)** | `<TOTAL_INLINE>` total · `<UNRESOLVED>` unresolved |
| **PR-level discussion comments** | `<N>` comments |
| **CODEOWNER / maint review status** | `Owner @<login> has CHANGES_REQUESTED open → CANNOT RECOMMEND APPROVE without 0C/0H + override justification` |

### Top unresolved human threads (≥3 listed with context)

1. **#comment-123456** by @octocat · `src/refund/service.ts:142` · UNRESOLVED · **"Missing idempotency key header on Stripe refund call — id collision risk if retry."**
2. **#comment-123457** by @alice · `apps/platform/app/admin/refunds/page.tsx:88` · UNRESOLVED · **"Admin UI shows raw customer email; repo convention says use hashPII(email) in admin tables too."**

---

## 🤝 Findings Alignment with Human Comments (non-duplication guarantee)

> Every finding ≥ MEDIUM must be classified against existing human threads. NÃO DUPLIQUE achados que humanos já levantaram (exceto para estender/discordar com justificativa explícita + cross-ref URL).

| Finding # | Classification | Cross-ref (thread id + author) | Justification when extends / disagrees |
|---|---|---|---|
| #F-1 🔴 CRITICAL (runtime) | **NOVO (não mencionado por nenhum revisor humano)** | — | Null deref é um caso edge novo descoberto em `renderPhone()` quando profile = null. Não conflita com as threads abertas existentes. |
| #F-2 🟠 HIGH (Security / PII) | **EXTENDS human thread #comment-123457** (concorda parcialmente) | `#comment-123457` by @alice · [thread URL] | @alice mencionou só admin UI table; extendemos PARA logger também (linha adicional `logger.info({email:...})` em `RefundService.ts:211` não comentada). A correção recomendada cobre ambos os locais. |
| #F-3 (exemplo) | **OMITIDO (duplicata exata)** | `#comment-123456` by @octocat | Idempotency key já levantado por @octocat; nenhuma informação adicional a acrescentar. 🎯 Reportado em "Existing Review Context" acima — não duplicamos aqui. |
| #F-4 (exemplo) | **DISCORDA parcialmente de humano** | `#comment-999999` by @bob · [thread URL] | @bob recomendou `dayjs()` → `date-fns` em 3 locais; análise mostra que `date-fns-tz` não seria necessário e que dayjs com `.tz()` plugin existente resolve. Recomendação contrária: manter dayjs + adicionar plugin tz (1 linha, sem new dep). |

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

### #F-5 🟡 MEDIUM — Category: Testing Gaps (G7.3) — `packages/platform/server/__tests__/e2e/refundFlow.api.test.ts:78-111`

**Why it matters:**
- New test case `"refund pending booking with settled Stripe capture"` (lines 78-111) does **NOT** have the mandatory traceability comment as the first line inside the `it()` block. SbE verification matrix §5 (ONDA2) relies on regex match `// @(ac|ticket|task|bug) B-\d+|FLO-\d+` inside every new/modified `it()` body to prove B-ID → test file bilateral coverage. Without it, scope-checker CHECK2 flags the behavior as "implemented but unverified" and score drops.
- Isolated bug: 1 of 6 new test blocks missing the anchor — not systemic.

**Diff snippet:**
```diff
@@ -78,6 +78,7 @@ it("refund pending booking with settled Stripe capture", async () => {
+    // @ac B-3 | @ticket FLO-513
     const { booking } = await seedBooking({ status: "pending_settlement" })
```

**Recommended fix (1-line drop-in):**
```typescript
it("refund pending booking with settled Stripe capture", async () => {
  // @ac B-3 | @ticket FLO-513
  // @bug regression: v2.1.4 allow double-capture edge
  const { booking } = await seedBooking({ status: "pending_settlement" })
  // ... rest unchanged
```

---

### #F-6 🟠 HIGH — Category: UI Selector Contract Hygiene (G8.1) — `packages/platform/components/creator/creator-bookings/RefundBookingAction.tsx:55-72`

**Why it matters (HIGH — affects perenidade de UI Playwright tests):**
- New `RefundConfirmButton` (icon-only spinner button, lines 55-72) is rendered **without `aria-label` + without `data-testid`**. Because it's: (a) an icon button (ByRole('button') has no accessible name — TextNode = undefined, empty string); (b) mounts a spinner overlay (LoadingSpinner = renders same role during async); (c) sits inside a table row where 4 other sibling action buttons exist (edit / resend ticket / cancel / refund). This is the exact G8.1 case where Testing Library priority order breaks: **no stable selector exists.** A Playwright or RTL test will fallback to `.getAllByRole('button')[3]` — which is fragile (G8.2 anti-pattern) and silently breaks the moment someone adds a 5th sibling action (e.g. `print invoice`) next sprint.

**Kent Dodds Testing Library priority applied to this exact button:**
1. ❌ ByRole('button', { name: /confirm/i }) — no name, icon-only.
2. ❌ ByLabelText — not a form field.
3. ❌ ByPlaceholderText — N/A.
4. ❌ ByText('Confirm refund') — JSX conditional hides label when loading.
5. ❌ ByDisplayValue/AltText/Title — none present.
6. ✅ ByTestId = only stable option here → but **missing in current diff**.

**Recommended fix (G8.1 compliant: aria-label FIRST [screen readers] + data-testid SECOND [tests]):**
```diff
@@ -60,8 +60,11 @@
   : (
     <button
+      aria-label="Confirm refund"
+      data-testid="refund__action-btn__confirm"
       onClick={handleConfirm}
       className="flex items-center gap-1"
     >
```

**Note on isenções:**
- This finding CANNOT be exempted via QA_OVERRIDE because it's an icon button in a table row with multiple siblings (3/3 G8.1 HIGH triggers simultaneously). If user wants override, they must sign `QA_OVERRIDE=G8.1 FLO-513: action button only appears once per screen today with no plan to add siblings` in the PR body, explicitly.

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
| **🟢 7. Testing Gaps & Regression Lock (G7.1 HIGH src 20+ln no test / G7.2 HIGH API+UI new without integ or Playwright / G7.3 MEDIUM @ac/@ticket traceability comment missing / G7.4 LOW skip without TODO)** | ✅ Yes — diff matched dirty src vs test files | 42 src lines added in `RefundService.ts` + 2 tests written (`refundFlow.api.test.ts` + `RefundBookingAction.spec.ts`) · traceability comments G7.3 validated in every new `it()` block |
| **🟣 8. UI Selector Contract Hygiene & data-testid 3-part (G8.1 HIGH interactive no data-testid fragile / G8.2 HIGH test selector XPath/nth/css-class / G8.3 MEDIUM non-standard regex / G8.4 LOW map-loop no unique suffix)** | ✅ Yes — every interactive component checked | Kent C. Dodds Testing Library priority order enforced; 5 new data-testids created (`refund__action-btn__confirm`, `refund__status-toast__success` etc); XPath/nth-child not used once; 0 duplicates in ticket line-item map |
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
