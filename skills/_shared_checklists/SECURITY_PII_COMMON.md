# SHARED CHECKLIST — Security & PII Compliance (CANONICAL)

> REFERÊNCIA COMPARTILHADA por: harness-compliance, harness-code-review, harness-ship (light per-task check), harness-pr-comments, harness-ci-fixer (secrets rotation check), harness-developer (per-implementation self-check).
> NÃO duplique o conteúdo abaixo em skills individuais. Referencie apenas este arquivo.

---

## 1. Secrets Leak Prevention (MANDATORY scan on every PR)

Scan ALL staged/new files for:
- Raw API keys (Stripe `sk_`, Supabase `service_role`, Resend `re_`, AWS `AKIA`, OpenAI `sk-`).
- Private keys / certificates (`BEGIN PRIVATE KEY`, PEM blocks).
- Hardcoded passwords, JWT tokens, session cookies.
- `.env` / `.env.local` files NEVER committed. Confirm `.gitignore` exists for `*.env*`.

If found ANY:
1. BLOCK gate immediately — DO NOT ship/approve.
2. Remove or replace with env var references.
3. If a secret was actually committed to git history (even once):
   - Recommend immediate rotation upstream (provider dashboard).
   - Log incident + remediation action taken to `decisions.log.jsonl`.

---

## 2. PII (Personally Identifiable Information) — UK GDPR

### 2.1 Never raw-log / raw-persist these categories:
- Email addresses (full inbox). Hash with `NOTIFICATION_PII_HASH_SECRET` for correlation.
- Phone numbers, full names, street address, date of birth.
- Payment card numbers (use Stripe/PSP tokens — never card PAN).
- IP addresses (anonymize last octet if retained; 1 day retention max usually).
- Ticket buyer full name/email combo.

### 2.2 Allowed when necessary:
- Hashed values with dedicated secret (store hash only; never commit secret anywhere).
- Masked values: `***@domain.com`, `+44 *** *** 1234`.

### 2.3 DB persistence checklist for any new PII-containing column:
- GDPR retention period declared on entity (e.g. `deleted_at` + 6-year retention or 90 days after event_date + hard delete).
- Export + delete (right to be forgotten) path considered.
- Column NOT selected by default in list endpoints (e.g. admin list endpoints hide emails; only show on detail view with justification).

---

## 3. Supabase Postgres RLS DEFAULT (see also engineering-contracts §17)

For EVERY new/migrated table:
1. `ALTER TABLE <schema>.<table> ENABLE ROW LEVEL SECURITY;` present.
2. Explicit `CREATE POLICY` statements per role (organizer / admin / anon / authenticated).
3. Default deny: with RLS enabled and zero policies, NO rows can be read/written. This is the desired starting state.
4. Exceptions ONLY when:
   - Pure enum/reference/lookup table, immutable, public data for everyone.
   - AND logged + user approved in `decisions.log.jsonl` (two confirmations: Non-Goals + explicit user OK).

---

## 4. Auth / Permission checks

- Admin-only endpoints have explicit role guard; 403 on permission denied.
- Organizer scoped endpoints (event/ticket CRUD): verify that `organizer_id` of the row matches `session.user.id`; otherwise 403/404.
- Role-based permission denied is an EXPLICIT Acceptance Criterion (per PRD G7 gap check).
- Double-click / retry idempotency: `Idempotency-Key` header or unique constraint prevents duplicate orders/payments (per PRD G6 gap check).

---

## 5. SQL injection / unsafe queries

- ORM/query builder preferred over raw SQL.
- Raw SQL ALWAYS uses parameterized queries (prepared statements). No string concatenation with user input into SQL.
- Never expose user-controlled sort/filter columns directly without a strict allowlist.

---

## 6. Output / HTTP response checklist

- Stack traces disabled in production responses.
- `404` preferred over `403` for "exists but you can't access" to avoid existence oracle (ex: ticket ID enumeration).
- CORS allowlist strict (no `*` in prod with credentials).
- CSRF protection present on state-changing endpoints when cookie auth used.

---

## 7. Authz Patterns Cross-File Audit (CRITICAL + HIGH checks; apply on any diff touching org-scoped procedures/services or authz calls)

### 7.1 Raw cookie org-check vs membership-validated context (CRITICAL for READ procedures; HIGH for WRITE procedures with mitigation)

**When to apply:** any router/procedure/handler that compares a scoped identifier (`ctx.activeOrgId`, `ctxOrgId`, `active_org` cookie value) against a row's `org_id` / `organization_id`.

> **MANDATORY — Analyze EACH procedure SEPARATELY. NEVER aggregate one procedure's mitigation onto another.**
> 
> Pre-step (before checking anything):
> - Liste TODOS os handlers/procedures NOVOS ou MODIFICADOS no router file (ex: bookingRouter tem `refundOrder` mutation + `getEligibleForRefund` query + `getBookingRefundStatus` query → 3 auditorias SEPARADAS).
> - Para CADA procedure individualmente: execute o procedimento abaixo.

**Procedure (per procedure):**
1. Read the context creation file (typical names / paths: `server/trpc.ts`, `server/context.ts`, `createContext.ts`).
2. Trace `ctx.activeOrgId` / equivalent source: is it raw from a cookie/header named `active_org`, or is it resolved after a DB membership check?
3. In the handler/service for THIS SPECIFIC PROCEDURE: confirm org membership is validated through **one of**:
   - `OrgContextService` call + DB membership row,
   - `authzService.assertCan(userId, "org:read"|"org:manage", { type:"org", orgId: rowOrgId }, authzCache)` or equivalent scoped permission check (call must appear INSIDE this procedure's handler; not in another sibling procedure),
   - a `whoami`-pattern membership query that returns only organizations the user belongs to,
   - OR a pure buyer fallback path (e.g. `row.userId === ctx.userId`) that grants access without org membership for user-owned rows.
4. **Severity por procedure (NÃO compartilhe):**
   - **CRITICAL se**: é um procedure **READ** (query `getEligibility`, `getStatus`, detail view, list pagination) e o gating é SOMENTE cookie↔row comparison SEM membership validada (sem assertCan/whoami/OrgContextService).
   - **HIGH se**: é um procedure **WRITE** (mutation) e o gating é cookie↔row SEM membership validada, MAS existem downstream guards DENTRO DO MESMO HANDLER (DB row locked + assertCan chamado com a orgId da TRUSTED row, não do cookie).
   - **LOW / Not flagged**: apenas se (a) assertCan é chamado ANTES do gating COM a orgId da row (não do cookie), OU (b) whoami revalidou membership, OU (c) 100% do acesso passa por buyer fallback path sem nenhum caminho de cross-org org-owned read.

**Why CRITICAL for reads:** any authenticated user can set the `active_org` cookie themselves → cross-org data exfiltration (payment amounts, Stripe refund IDs, buyer PII, event status). Exception: buyer fallback paths (e.g. `row.userId === ctx.userId`) that don't need org membership.

### 7.2 authzService.assertCan 4th-arg cache threading (HIGH if missing in router-callable service paths)

**When to apply:** any diff containing `.assertCan(userId, permission, resource)` or equivalent authz-check method.

**Procedure:**
1. Read the assertCan signature: does it accept a 4th optional `cache?: AuthzCache` parameter?
2. Read the router context: does `ctx.authzCache` exist (usually `new Map()` per request)?
3. Trace the call-chain from each router entrypoint → service(s): does every service thread `ctx.authzCache` (or a derived cache object) into every assertCan / permission-check invocation reachable from routers?
4. **HIGH if:** any router-reachable service path calls assertCan WITHOUT passing a cache.

**Why HIGH:** uncached assertCan commonly re-issues an `isPlatformAdmin` DB query per call. Under N+1 pattern on list pages or batched mutations → latency spikes + DB load. Not a correctness bug but a production perf / availability bug.

### 7.3 Authz ordering — before write (CRITICAL if reversed)

- Authz checks run INSIDE each endpoint. They MUST run BEFORE any DB write, side effect, or PSP/PSP-like call.
- **CRITICAL if:** DB mutate / PSP call happens first, authz check runs after (even if failure rolls back — partial side effects, failed charges already recorded by the PSP, observable by customers).

---

## 8. Webhook Pipeline Entry Point Integrity Check (CRITICAL allowlist mismatch; never skip if diff touches webhook route or service)

### 8.1 Route-level allowlist vs service supportedTypes

**When to apply:** any diff touching files matching `webhook`, `Webhook*Service`, `*WebhookHandler`, `api/webhooks/**/route.ts`, OR any service that references `supportedTypes`, `handleStripe*`, `charge.*`, `customer.*`, `payment_intent.*`.

**Procedure:**
1. **Read the ROUTE-level dispatcher file** first — `/api/webhooks/*/route.ts` (or framework equivalent). Look for:
   - early allowlist arrays (e.g. `stripeSnapshotEventTypes`, `acceptedEvents`, `handledEventTypes`) declared near the top of the file,
   - any early-return `202 / ignored: true` / `return NextResponse.json({ignored: true}, {status:202})` branches,
   - dispatcher regex / switch statements.
2. **Read the SERVICE handler class.** Look for:
   - static arrays like `WebhookChargeRefundedService.supportedTypes = ['charge.refunded', …]`,
   - switch-case inside `handleEvent(type, ...)` that enumerates handled types.
3. **Cross-compare: service types ⊆ route allowlist?**
   - For every type handled by the service, is it present in the route's allowlist?
4. **CRITICAL if:** ANY service-handled type is MISSING from the route-level allowlist.

**Why CRITICAL:** the route is the only real entrypoint. Typical route pattern: if event type ∉ allowlist → return 202 "ignored" before the service is ever instantiated. The service handler never runs. Unit/E2E tests that call `svc.handleEvent('charge.refunded', payload)` directly PASS — they never exercise the allowlist gate. This produces "tests pass, prod silent-failure" for every allowlist-missing event.

**Remediation required on CRITICAL:**
- Add the missing event type(s) to the route allowlist,
- Add a route-level signed-payload POST test (not just a direct `handleEvent` call) that hits the real route with a valid signature and asserts the service ran + side effects applied.

### 8.2 PSP charge-model consistency audit (CRITICAL if contradiction)

**When to apply:** any diff touching `createPaymentIntent`, `createRefund`, `transfer`, `reverse_transfer`, PSP client options `stripeAccount`/`transfer_data.destination`/`on_behalf_of`/`application_fee_amount`.

> **PROCEDIMENTO 3-PASS OBRIGATÓRIO — NÃO PULE nenhum passo.**

#### Passo 1 — Extraia params de createPaymentIntent (literalmente):
Ache a linha onde `paymentIntents.create(...)` / `createPaymentIntent(...)` é chamada. Extraia textualmente:
- (a) **2º argumento (headers)**: existe objeto `{ stripeAccount: X }`? Anote `X` (ex: `payload.stripeConnectedAccountId`, uma expressão variável).
- (b) **1º argumento (body params)**: existe objeto `transfer_data: { destination: Y }` (ou linha `transfer_data.destination = Y`)? Anote `Y`.

#### Passo 2 — Detecte contradição no createPaymentIntent:
SE (a) E (b) forem AMBOS verdadeiros → compare as expressões `X` e `Y`.
- **CRITICAL se `X === Y` semanticamente** (mesma conta variável). Motivo: Stripe rejeita HTTP 400 a request cujo `transfer_data[destination]` é igual à conta que está fazendo a request (account in `stripeAccount` header). TODO checkout Connect existente quebra; 100% das orgs conectadas não podem processar pagamentos.

#### Passo 3 — Cross-check createPaymentIntent model × createRefund model:
Após Passo 2, classifique createPaymentIntent:
- **DESTINATION CHARGE**: só (b) é verdadeiro (apenas `transfer_data.destination` existe; sem `stripeAccount` header). Charge e PI vivem na **PLATFORM** account.
- **DIRECT CHARGE**: só (a) é verdadeiro (apenas `stripeAccount` header existe; sem `transfer_data.destination`). Charge e PI vivem na **CONNECTED** account.

Agora ache `createRefund(...)` ou `refunds.create(...)`:
- (r1) Tem `stripeAccount: R` como header/2º arg?
- (r2) Tem `reverse_transfer: true`?

Contradições adicionais (TODAS CRITICAL):
- **Destination Charge model + createRefund com stripeAccount=connected + reverse_transfer=true** → CRITICAL. Motivo: `reverse_transfer` só tem efeito em refunds emitidos DA PLATFORM (sem stripeAccount). createRefund com stripeAccount connected procura o charge/pi DENTRO da connected account — mas destination-charge PIs vivem na platform → Stripe 404 "charge not found".
- **Direct Charge model + createRefund SEM stripeAccount + COM reverse_transfer=true** → CRITICAL. Motivo: direct charge não teve nenhum transfer_data; reverse_transfer=true não faz sentido. E sem stripeAccount o refund cai na platform account procurando um charge que não existe lá.

**Formal classification (after running 3-pass):**
- **Destination charge model:** PaymentIntent created ON the platform account (NO `stripeAccount` param on create); `transfer_data.destination = connected`, `application_fee_amount`, `on_behalf_of` present; refunds issued from the platform with `reverse_transfer: true`.
- **Direct charge model:** PaymentIntent created WITH `{ stripeAccount: connectedAccountId }` header; NO `transfer_data.destination` (the PSP rejects if destination equals the requester); refund issued with the same `stripeAccount` header.

**CRITICAL if ANY of the 3-pass contradictions exist:**
1. `createPaymentIntent` carries `stripeAccount` (direct) but ALSO sets `transfer_data.destination = same account` → PSP request fails. Every Connect checkout using that method breaks.
2. `createRefund` carries `stripeAccount:` (direct charge refund style) AND ALSO `reverse_transfer: true` — reverse_transfer only applies to destination-charge model; wrong-ID-namespace errors when PI/Refund IDs live on platform vs connected account.

**Why CRITICAL:** mocks in tests often bypass real request validation → tests pass green; every real Connect request fails on prod.

**Remediation:** pick ONE charge model end-to-end for each flow; keep PaymentIntent and Refund parameterization consistent. Add an unmocked integration test (against the real SDK validator OR with a typed mock that rejects contradictory params).

