# PR DESCRIPTION TEMPLATE

> Used by `harness-ship` when creating a GitHub DRAFT PR.
> Language: **ENGLISH by default.** Only write PR body in another language IF the user EXPLICITLY requests otherwise in the same message (e.g., "escreve PR em PT-BR"). No guessing.
> Body size budget: **30 lines or fewer, TOTAL** (trim, trim, trim). No breaking → ~20 lines. With breaking → ~30 lines.

---

## What was implemented

<!-- 3-6 bullets MAX. Each bullet = one concrete change. No paragraphs. -->

- ...
- ...
- ...

## 🔍 Attention points

<!-- What reviewers MUST pay attention to. 3 bullets ideal, 5 max.
     Format per bullet: **Risk area:** `path/to/file.ts` — 1 sentence why.
     Risk areas: Security-sensitive / Performance-sensitive / Blast-radius (DDL migration) / Cross-module coupling / Concurrency correctness -->

- **Security-sensitive:** `packages/auth/src/...` — JWT role check added for the new admin endpoint
- **Blast-radius risky:** migration `YYYYMMDD-name.sql` — adds index to high-traffic `ticket_scans` table
- **Cross-module:** touches `@flockr/db` entity + `@flockr/platform` service together; confirm coupling is intentional

## 💥 Breaking changes

<!-- ONLY include this block when breaking changes EXIST.
     If NONE → DELETE this entire "Breaking changes" section (do NOT write "NONE"). -->

### `POST /api/v1/payments/refund` — body schema change
- **Before:** `{ ticketId }` (ticket inferred payment implicitly)
- **After:** `{ ticketId, paymentId }` (explicit, 400 if missing)
- **Migration:** Update callers to pass `paymentId` from the order record

## 🧪 How to verify

<!-- 1-3 bullets: Unit + E2E first, then 1 quick manual sanity.
     Unit/E2E = concrete command pointing to specific test.
     Manual = 2-3 steps, concrete, no vagueness. -->

- **Unit:** `corepack pnpm nx run db:test --tui false -- src/refund-pipeline.test.ts` (covers refund eligibility + ledger entries)
- **Manual:** (1) `pnpm nx run platform:dev`, (2) open event `FLO-513-sandbox`, (3) refund a paid ticket → dashboard shows "Refunded" + ledger debit line visible
- **Full plan:** `./.trae/FLO-513-refund/manual_test_plan.md`

## 🔗 Refs

- **Linear ticket:** `FLO-123` — https://linear.app/flockr/issue/FLO-123/slug
