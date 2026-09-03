# PR DESCRIPTION TEMPLATE

> Used by `che-ship` when creating a GitHub DRAFT PR.
> Language: **ENGLISH by default.** Only write PR body in another language IF the user EXPLICITLY requests otherwise in the same message (e.g., "escreve PR em PT-BR"). No guessing.
> Body size budget: **≤50 lines TOTAL, IDEAL ~35–45.** No breaking → ~30 lines. With breaking → ~45 lines. If over budget → move long details to a linked doc + keep 1 summary line here.
>
> **READABILITY RULES (non-negotiable — person with little project context should understand):**
> 1. **Acronyms expanded on first use** (example: "RLS (Row-Level Security — Postgres access rules)" not just "RLS").
> 2. **Every "What was implemented" bullet = 1 short sentence WHAT changed + 1 short sentence WHY / end-user impact.** No 10-item concatenated bullets.
> 3. **Avoid internal jargon** without ½-line context (example: "reverse_transfer (Stripe Connect — money returns from the connected account back to platform)" not just "reverse_transfer=true").
> 4. **Attention points = explain the CONSEQUENCE if review misses it.** Not only "Risk area: migrations" — say "Risk: if this schema script fails in prod, the new refund feature cannot be used by anyone."
> 5. **How to verify = step-by-step that a non-dev can run.** No assumed knowledge of internal folder structure.

---

## What was implemented

<!-- 3–8 bullets, each = one self-contained change. No paragraphs.
     Pattern per bullet: `feat(scope): <WHAT in plain English>. <WHY / user impact>.`
     If >8 items → PR is too large (split into a gh-stack, see che-ship §Path B). -->

<!-- ⬇️ REAL EXAMPLE below (the same refund feature from the screenshot, rewritten for low-context readers). KEEP this example visible so agents copy this style, then replace with actual content. ⬇️ -->

- `feat(db): added a new "Refunds" database table + 5 schema update scripts (DDL).` Why: stores every refund request with its Stripe reference and status (Processing → Completed / Failed). Includes RLS (Row-Level Security — Postgres access rules) so each organization can only see its own refunds.
- `feat(db): new Refund data entity + idempotency composite key (orgId + orderId).` Why: prevents the same order from being refunded twice by accident, even if two admins click "Refund" at the same time.
- `feat(platform): RefundService — a 3-step pipeline to process refunds safely.` Why: marks the order as "Processing" FIRST (before calling Stripe), then charges the refund, then sends the confirmation email. This avoids race conditions with Stripe's webhook notifications. Uses a 2-tier safety check (database lock + Stripe idempotency key valid for 120 seconds).
- `feat(platform): Stripe integration — createRefund API + charge.refunded webhook handler.` Why: actually moves the money back to the customer via Stripe Connect (reverse_transfer — money returns from the connected event-organizer account back to the platform, then to the buyer). The webhook handler has 4 duplicate-detection paths so it never double-processes the same Stripe event.
- `feat(platform): new API endpoint (tRPC bookingRouter.refundOrder) + creator dashboard UI button.` Why: lets event organizers click a button "Refund order" on an existing booking. A confirmation pop-up checks eligibility (order must be paid, event must be refundable) before proceeding.
- `feat(platform): Refund confirmation email via Resend + full E2E test (refundFlow.api.test.ts).` Why: customer receives a confirmation email after refund. The E2E test (using a real Postgres via Testcontainers) creates a booking → requests refund → verifies final status → confirms duplicate webhook is ignored. Test passes 1/1.

## 🧭 SbE Traceability Matrix

> **Auto-preenchida quando SPEC SbE for aprovado e `// @ac B-X` anchors forem extraídos do diff. Se for spec legado (sem B-IDs) → REMOVER ESTA SEÇÃO INTEIRA no PR real.**
>
> Cada linha = um behavior B-ID ou anti-behavior AB-ID aprovado na §4.2 Behavior Table da SbE spec. Coverage < 70% → ver action items do scope-checker CHECK2 bilateral.

| Behavior ID (B ou AB) | Test file path (extraído de `// @ac B-X` anchors no diff — include :line-range se for bloco it()) |
|---|---|
| B-1 | `packages/platform/server/__tests__/e2e/refundFlow.api.test.ts:112-145` |
| B-3 | `packages/payments/services/__tests__/RefundService.unit.test.ts:45-60` |
| AB-2 | `packages/platform/server/__tests__/integration/refundIdempotency.integ.test.ts:22-38` |

> **Coverage audit rule:** Se a §4.2 Behavior Table da SbE listar 10 B-IDs e esta tabela só tiver 6 → coverage = 60% → warning G7.3 em Category7 do code-review (upgrade para HIGH se ≤2 HIGH gate).

## 🔍 Attention points

<!-- What reviewers MUST pay attention to. 3 bullets ideal, 5 max.
     Pattern per bullet: **Risk area:** `path/or filename` — <what's risky>. **If review misses this:** <consequence in plain English>.
     Risk area categories: Security-sensitive / Performance-sensitive / Schema change (DDL migration) / Cross-module change / Concurrency (race conditions). -->

<!-- ⬇️ REAL EXAMPLE below. Same feature. KEEP visible as style reference. ⬇️ -->

- **Schema change (DDL):** `packages/db/migrations/` 5 files (M-1…M-5) — new Refunds table + RLS policies + indexes + enum additions. **If review misses this:** must be run against STAGING database FIRST and review the migration plan output. If the script breaks in production, nobody can use the refund feature until a DBA fixes it.
- **Concurrency / race condition:** `RefundService.ts` + `IdempotencyKeyRepository` — 2-tier idempotency with a 120-second Stripe idempotency window. **If review misses this:** in the rare case Stripe's webhook arrives BEFORE the createRefund API response returns, the order might get stuck in "Processing" forever or duplicate the refund. Double-check the dedup logic when the 120s Stripe window expires.
- **Product decision (intentional partial-refund rejection):** `StripeWebhookService.handleChargeRefunded` 4-path matcher. Partial refunds are intentionally NOT supported — code throws `RefundCapabilityError` with a distinct error code so callers can route differently. **If review misses this:** confirm product team still wants "no partial refunds." Do NOT silently swallow this error — operators will never notice Stripe refunded half the money but our DB still shows full amount.

## 💥 Breaking changes

<!-- ONLY include this block when breaking changes EXIST.
     If NONE → DELETE this entire "Breaking changes" section (do NOT write "NONE").
     When included: 1 heading per breaking + Before / After / Migration bullets. -->

### `POST /api/v1/payments/refund` — body schema change
- **Before:** `{ ticketId }` (payment was implicitly inferred from the ticket)
- **After:**  `{ ticketId, paymentId }` (explicit — returns 400 Bad Request if `paymentId` is missing)
- **Migration:** All clients calling this endpoint must now pass `paymentId`, available on the order record.

## 🧪 How to verify

<!-- 1–3 bullets, in this order:
     (a) Automated tests — concrete command pointing to a SPECIFIC test file + what it covers
     (b) Quick manual check — 2–3 concrete steps (no "test it works" vague stuff)
     (c) Optional: full manual test plan link
     Every step should be runnable by a reviewer with LITTLE project context. -->

- **Automated (E2E):** `corepack pnpm nx run platform:test --refundFlow  # runs refundFlow.api.test.ts` — covers: create paid booking → request refund → verify final DB state → send duplicate webhook → verify it's a no-op. Expected result: 1 test suite, 1/1 passing (green).
- **Quick manual:** (1) `corepack pnpm nx run platform:dev` → (2) login as a creator, open any paid booking → (3) click **Refund order** in the booking dashboard. Expected result: button is disabled if ineligible; confirmation modal appears; after confirm, booking status changes to "Refunded" and a confirmation toast is shown.
- **Full plan (if needed):** `$CHE_WORKSPACE_SHARED/manual_test_plan.md`

## 🔗 Refs

- **Issue tracker:** `PROJ-123` — https://linear.app/myorg/issue/PROJ-123/refund-orders-for-event-creators
<!-- Optional: 1 extra link. Figma design, PRD .md path, related PR number. -->
