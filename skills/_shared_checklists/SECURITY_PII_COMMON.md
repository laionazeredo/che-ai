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
   - Log incident + remediation action taken to `decision.log.md`.

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
   - AND logged + user approved in `decision.log.md` (two confirmations: Non-Goals + explicit user OK).

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
