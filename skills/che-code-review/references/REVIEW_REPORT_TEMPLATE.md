# REVIEW REPORT TEMPLATE (for PRs)

> Used by `che-code-review` when it finishes analyzing a GitHub PR.
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

> Every finding ≥ MEDIUM must be classified against existing human threads. DO NOT DUPLICATE findings that humans have already raised (except to extend/disagree with explicit justification + cross-ref URL).

| Finding # | Classification | Cross-ref (thread id + author) | Justification when extends / disagrees |
|---|---|---|---|
| #F-1 🔴 CRITICAL (runtime) | **NEW (not mentioned by any human reviewer)** | — | Null deref is a new edge case discovered in `renderPhone()` when profile = null. Does not conflict with existing open threads. |
| #F-2 🟠 HIGH (Security / PII) | **EXTENDS human thread #comment-123457** (partially agrees) | `#comment-123457` by @alice · [thread URL] | @alice mentioned only admin UI table; we extended TO logger as well (additional line `logger.info({email:...})` in `RefundService.ts:211` not commented). Recommended fix covers both locations. |
| #F-3 (example) | **OMITTED (exact duplicate)** | `#comment-123456` by @octocat | Idempotency key already raised by @octocat; no additional info to add. 🎯 Reported in "Existing Review Context" above — we don't duplicate here. |
| #F-4 (example) | **DISAGREES partially with human** | `#comment-999999` by @bob · [thread URL] | @bob recommended `dayjs()` → `date-fns` in 3 locations; analysis shows `date-fns-tz` wouldn't be necessary and existing dayjs with `.tz()` plugin resolves it. Contrary recommendation: keep dayjs + add tz plugin (1 line, no new dep). |

---

## Context Bootstrap Evidence (TRANSPARÊNCIA OBRIGATÓRIA — what files we actually read BEFORE reviewing the diff)

User must be able to verify that the review was context-aware (not superficial diff-only eyeballing). Fill this section IN EVERY REPORT. If a file says "(N/A — doesn't exist in repo)" it still counts as checked; if blank = review is invalid.

| Bootstrap item (§1.5 framework) | Files actually read / checked |
|---|---|
| `che review rules` (§1.5.0) | ran on `<worktree>` with `<n>` changed paths → `<n>` sources, `<n>` applicable rules, `<n>` conflicts, `<n>` drift |
| R1 Root README.md | |
| R2 docs/plan.md | |
| R3 docs/decisions.md or docs/adr/*.md (last 5) | |
| R4 graphify-out/GRAPH_REPORT.md | (N/A or path) |
| R5 Package README.md / docs/<area>.md (affected areas) | `packages/platform/README.md`, `docs/platform.md` |
| R6 Local project review skill (MANDATORY glob — never "if exists") | `<glob output: path1, path2>` read fully; `<n>` checklist checks mapped to Categories (see R6 mapping table) |
| §1.5.6 Pattern mining | `<n>` artefact types · exemplars: `<file:line>`, `<file:line>` |
| Cross-file pipeline reads (MANDATORY if diff matches keywords): <br> — Webhook route allowlist <br> — ALL PSP/Connect charge methods in the package | `app/api/webhooks/stripe/route.ts:7-16` (allowlist read) <br> `StripeClient.ts:285-313` (createPaymentIntent) + `RefundService.ts:~450` (createRefund) read |

### R6 mapping table (every project-checklist check → Category)

> A check with no Category is a GAP IN THIS SKILL. Route it to Category 9 and add one `SKILL GAP: <check> — no Category owns it` line below. Never write "none found" without showing the glob output.

| Project check (source:line) | Category | Applied? |
|---|---|---|
| `<checklist file:line — check name>` | `<Category N or 9.x>` | `<APPLIED → F-n / NO_MATCH>` |

---

## ⚖️ Rule Resolution (one block — never per finding)

> Filled from the resolver JSON. An omitted block invalidates the review: the reader cannot tell which authority produced the verdict.

| Item | Value |
|---|---|
| **Sources** | `<n>` read · `<n>` applicable · `<n>` path-scoped out · `<n>` below `min_severity` · `<n>` over budget |
| **Params in force** | `min_severity=<X>` · `blocking=<CRITICAL,HIGH>` · `ignore_paths=<…>` · `max_rules=<n>` |
| **Precedence** | `<topic>`: winner `<source:line>` ⟶ loser `<source:line>` (superseded) |
| **Drift** | `<topic>`: repo rule `<source:line>` ≠ Che project memory `<source:line>` |
| **Unresolved conflicts** | `<topic>`: `<source:line>` vs `<source:line>` — both capped at MEDIUM, non-blocking |
| **Hard floor** | `<n>` invariants in force (never overridable) |

If nothing was found: write `no contradictions detected` explicitly. Never leave the block out.

---

## Rule accounting (one row per source file — never per rule)

> Every rule whose `scope` matches a changed path AND whose `effective_severity` is CRITICAL or HIGH must be APPLIED (with its finding) or NO_MATCH. Anything else is OUT_OF_SCOPE(path). A rule in none of the three means the review is incomplete.

| Source file | Rules | APPLIED | NO_MATCH | OUT_OF_SCOPE |
|---|---|---|---|---|
| `<architecture.md>` | `<3>` | `<2 — F-3>` | `<1>` | `<0>` |

**Stated limitation:** accounting does not create depth — a path-scoped rule that does not match the diff still cannot see the defect. Depth comes from Category 9.

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
- New test case `"refund pending booking with settled Stripe capture"` (lines 78-111) opens with `// @ac B-3 | @ticket FLO-513`. The body of the test now depends on two planning artefacts (`B-3` in the SPEC §4.2 table and ticket `FLO-513`) to be understood. Whoever reads the CI report in six months — or a new hire opening the file — cannot tell what is arranged, which input is used or what the invariant is.
- Isolated case: 1 of 6 new test blocks carries the anchor — not systemic.

**Diff snippet:**
```diff
@@ -78,6 +78,7 @@ it("refund pending booking with settled Stripe capture", async () => {
+    // @ac B-3 | @ticket FLO-513
     const { booking } = await seedBooking({ status: "pending_settlement" })
```

**Recommended fix (drop-in):**
```typescript
it("refund pending booking with settled Stripe capture", async () => {
  /**
   * Seeds a booking awaiting settlement, requests a full refund and expects
   * the capture to be reversed, the row to move to "Refunded" and exactly
   * one Stripe transfer to be returned to the platform account.
   */
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

**Note on exemptions:**
- This finding CANNOT be exempted via QA_OVERRIDE because it's an icon button in a table row with multiple siblings (3/3 G8.1 HIGH triggers simultaneously). If user wants override, they must sign `QA_OVERRIDE=G8.1 FLO-513: action button only appears once per screen today with no plan to add siblings` in the PR body, explicitly.

---

## Coverage of Review (transparency — what we checked)

User should trust we actually ran the full process:

| Category framework item | Checked? | Evidence from bootstrap |
|---|---|---|
| §1.5 Project Rule Resolution (`che review rules` + R1-R6 context + Cross-file pipelines) | ✅ Yes — see "Context Bootstrap Evidence" and "⚖️ Rule Resolution" above | |
| 0. Cross-File Pipeline Integrity (0.1 webhook allowlist / 0.2 3-pass Connect charge-model audit / 0.3 tx+locks overlap / 0.4 fire-and-forget Vercel) | ✅ Yes | Files read: `route.ts` allowlist, `StripeClient.ts` PI params 3-pass check, `RefundService.ts` tx span, setImmediate email paths |
| 1. Runtime breakage / silent incorrect behavior + Crash-safety PROCESSING row + substring vs error.code + circular imports + index drift + idempotency null-cast | ✅ Yes — diff all files line-by-line | |
| 2. Security / PII / Compliance (LIGHT level + **per-procedure READ/WRITE split** authz audit 2.8-2.10 — cookie org check + assertCan cache threading + authz BEFORE writes) | ✅ Yes | Each procedure audit: `trpc.ts:46-49`, `context.ts:51` + `bookingRouter` 3 procedures scanned SEPARATELY |
| 3. Architecture layering / Repo boundary **(per-procedure direct repo instantiation check)** + **Migration Hygiene (timestamps fabricated/intra-branch patch/RLS TO PUBLIC defaults)** + Entity dupe + deps scope | ✅ Yes | Router business logic + direct repo instantiation scanned per procedure; 5 migration files scanned for fabricated timestamps/intra-branch enum patch |
| 4. Scope deviation / **UI demo 5-pass scan** (fake latency + random fail + discarded idempotencyKey + toast no API call + demo data imports) / test naming rules / 4.8 route-level test gaps | ✅ Yes — ACs mapped to changed files | RefundBookingAction.tsx 5-pass demo check applied; test behavioral naming rules validated |
| **🟢 7. Testing Gaps & Regression Lock (G7.1 HIGH src 20+ln no test / G7.2 HIGH API+UI new without integ or Playwright / G7.3 MEDIUM planning reference in test title or comment / G7.4 LOW skip without TODO)** | ✅ Yes — diff matched dirty src vs test files | 42 src lines added in `RefundService.ts` + 2 tests written (`refundFlow.api.test.ts` + `RefundBookingAction.spec.ts`) · titles and comments checked for self-containment (no @ac/@ticket/@task) |
| **🟣 8. UI Selector Contract Hygiene & data-testid 3-part (G8.1 HIGH interactive no data-testid fragile / G8.2 HIGH test selector XPath/nth/css-class / G8.3 MEDIUM non-standard regex / G8.4 LOW map-loop no unique suffix)** | ✅ Yes — every interactive component checked | Kent C. Dodds Testing Library priority order enforced; 5 new data-testids created (`refund__action-btn__confirm`, `refund__status-toast__success` etc); XPath/nth-child not used once; 0 duplicates in ticket line-item map |
| **🟠 9. Repository convention conformance (9.1 constants/config placement · 9.2 existing-pattern reuse · 9.3 copy/localisation · 9.4 semantic markup · 9.5 stale identifiers)** | ✅ Yes / N/A | R6 checklist mapped · exemplars compared per §1.5.6 |
| Non-goals (style / formatting / naming / coverage %) | ⚠️ Skipped intentionally — that's CI/lint job | |

---

## Final user-facing recommendation

**(Written in Portuguese in the actual chat delivery; this template records what was checked.)**

Blocking:
1. Fix F-1, F-2 + F-6 before merge.
2. Decide on F-3: scope creep (remove or justify).

Non-blocking nice-to-haves:
- F-4 (deps) — up to you.
- F-5 (self-contained test comment) — up to you.

After fixes: re-run a short follow-up review, then OK to move to /che-ship or merge.

---

## 🎯 COMMENT MATRIX — copy-paste block (LAST section — hard rules in SKILL.md §4-O)

> Ask the comment language first (§O.1) and record it as `COMMENT_LANG`. Then one matrix row per finding, blocking severity first, SAME order as "Findings". The user copies THIS section, not the report above.

**COMMENT_LANG:** `English` / `Português (pt-BR)` / `mirror the PR discussion`

| # | Severity | Blocking | Path | Line | Side | Comment |
|---|---|---|---|---|---|---|
| F-1 | 🔴 CRITICAL | yes | `packages/platform/components/payment-stripe/stripe-checkout-page.tsx` | 133 | RIGHT | Since `applyDiscountCode` no longer patches the PaymentIntent server-side, this total is only what the buyer sees and `stripe.confirmPayment` will charge more than shown. That is why this blocks approval — recreating the PaymentIntent at confirm time would keep the charge aligned with the total. |
| F-2 | 🟠 HIGH | yes | `packages/notification/src/email-service.ts` | 211 | RIGHT | Thanks for wiring the notification flow — the raw customer email is going into an info log here, and the repo already ships `hashPII()` for correlation. This is why I cannot approve yet: swapping in the hash keeps notification logging consistent with the rest of the codebase. |
| F-3 | 🟡 MEDIUM | no | `packages/notification/src/email-service.ts` | 88 | RIGHT | Nice cleanup overall — just a small suggestion you can ignore: extracting the template lookup into a helper would keep this method under the 30-line guideline. |

### #F-1 · 🔴 CRITICAL · Runtime breakage

**Where:** `packages/platform/components/payment-stripe/stripe-checkout-page.tsx:133` (RIGHT)

**Explanation (PT):** O desconto deixou de ser aplicado no PaymentIntent no servidor, portanto o total mostrado já não é o que vai ser cobrado.

**GitHub comment (`COMMENT_LANG`):** the literal matrix text for F-1.

**Post command:**

```bash
gh api repos/<OWNER>/<REPO>/pulls/<PR_NUMBER>/comments \
  -f body='Since `applyDiscountCode` no longer patches the PaymentIntent server-side, this total is only what the buyer sees and `stripe.confirmPayment` will charge more than shown. That is why this blocks approval — recreating the PaymentIntent at confirm time would keep the charge aligned with the total.' \
  -f path='packages/platform/components/payment-stripe/stripe-checkout-page.tsx' \
  -F line=133 -f side='RIGHT' \
  -f commit_id="$(gh pr view <PR_NUMBER> --repo <OWNER>/<REPO> --json headRefOid -q .headRefOid)"
```

### #F-2 · 🟠 HIGH · Security / PII

**Where:** `packages/notification/src/email-service.ts:211` (RIGHT)

**Explanation (PT):** E-mail do comprador em texto simples a entrar num log de nível info, quando o repositório já tem `hashPII()` para correlação.

**GitHub comment (`COMMENT_LANG`):** the literal matrix text for F-2.

**Post command:**

```bash
gh api repos/<OWNER>/<REPO>/pulls/<PR_NUMBER>/comments \
  -f body='Thanks for wiring the notification flow — the raw customer email is going into an info log here, and the repo already ships `hashPII()` for correlation. This is why I cannot approve yet: swapping in the hash keeps notification logging consistent with the rest of the codebase.' \
  -f path='packages/notification/src/email-service.ts' \
  -F line=211 -f side='RIGHT' \
  -f commit_id="$(gh pr view <PR_NUMBER> --repo <OWNER>/<REPO> --json headRefOid -q .headRefOid)"
```

### #F-3 · 🟡 MEDIUM · Design Quality

**Where:** `packages/notification/src/email-service.ts:88` (RIGHT)

**Explanation (PT):** Método acima do limite de 30 linhas; extrair o lookup de template mantém a leitura simples.

**GitHub comment (`COMMENT_LANG`):** the literal matrix text for F-3 (non-blocking wording is mandatory at MEDIUM/LOW).

**Post command:** same shape, `line=88`, non-blocking body.

**Skipped:** 1 finding — #F-4 (scope deviation) is already answered in the PR body, so it needs no code comment.

> **Mode B (local worktree):** there is no PR. Emit the same matrix + five fields, leave the command in placeholder form, and add "run once a PR exists". Never fabricate a PR number.
