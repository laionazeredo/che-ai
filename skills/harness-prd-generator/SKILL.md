---
name: "harness-prd-generator"
description: "Creates a PRD (Product Requirements Document) following a strict repo template. Inputs: Linear/Jira ticket link OR free-text scope. First performs a CRITICAL deep repo analysis (performance, security, scalability, maintainability) for implications, then runs an iterative structured questionnaire to refine scope, cover edge cases, and fill every section of the PRD. Outputs the PRD following the exact 15-section template: Overview, Problem, Goals, Non-Goals, User Stories, FRs, NFRs, Data Model, System Interactions, Dedup, Normalisation, ACs, Open Questions. Invoke by /harness-prd command or when user asks to 'write a PRD' / 'create a spec'."
---

# Harness — PRD Generator (Critical, Evidence-Based)

This skill produces a **high-quality, complete PRD** strictly following the 15-section template at `docs/prd/_template.md`.
Its philosophy is **"critical first, creative second"**: before asking the user ANYTHING about the feature, it performs a **deep, evidence-based analysis of the target worktree/repo** for performance, security, scalability, maintainability implications, so the later questionnaire is grounded in reality, not generic product questions.

This skill is the **explicit replacement** for generic "write me a PRD" prompts.

---

## 0. NON-NEGOTIABLE PREFLIGHT

### 0.1 Worktree-first enforcement (copy from harness-scrum-master rule #1)
- If the request does NOT contain a **confimed, explicit, absolute worktree path** → `AskUserQuestion` immediately:
  - Q: "Qual worktree (caminho absoluto) você quer que eu use como base da análise + destino do PRD?"
  - Never proceed, never analyze, never write until user answers.
- Once provided: validate `ls -d <WORKTREE_ROOT>` works AND it has `.git/` or a `.git` file.

### 0.2 Input: one of (ticket link) XOR (free text scope) is REQUIRED
The user MUST provide either:
A) A **Linear ticket link** (https://linear.app/...) or **Jira ticket link** — API fetch to get title, description, assignee, labels, priority, ACs if any; OR
B) A **free-text scope description** (3+ sentences minimum) describing the idea/problem.

If neither → ask: "Você pode fornecer (1) link do Linear/Jira para o ticket OU (2) uma descrição em texto de 3+ frases do que é essa feature?"

### 0.3 Output path
- Ask the user: **"Onde você quer salvar o PRD?"**
  - Option A (DEFAULT if user says "default" / "onde tá certo" / blank):
    - Slugify the feature title → `prd-<slug>.md`
    - Save under: `<WORKTREE_ROOT>/.trae/<task-id>/prd-<slug>.md` (creates `.trae/<task-id>/` if missing).
  - Option B (repo canonical): `<WORKTREE_ROOT>/docs/prd/<area>/<slug>.md` if `docs/prd/` exists in the worktree (e.g., `docs/prd/payments/stripe-connect-dashboard.md`). Ask if user prefers this pattern; if yes, ask `<area>` folder name + slug.
  - Option C (absolute path): user provides any other absolute path (outside worktree is OK — we just write to disk, no commit).

### 0.4 PRD Header Metadata
Ask (only 4 simple fields, do NOT put into deep questionnaire):
- Feature name (1 line, 6 words max):
- Author name (for PRD attribution):
- Date (default: today ISO 8601 YYYY-MM-DD):
- Linear ticket URL (if ticket link not yet provided):
- Status default: `Draft` (only changes on user explicit say-so)

---

## 1. STEP 1 — CRITICAL DEEP REPO ANALYSIS (BEFORE ASKING THE USER QUESTIONS)

This is the UNIQUE selling point of this PRD harness vs generic PRD writers.

Goal: produce a structured repo analysis report, 4 dimensions × 3 sub-checks each, with evidence (file names, line refs) for every finding. The results INFORM every subsequent question in the questionnaire, so we don't ask "what about security" when the repo already has RLS everywhere, OR ask "what about race conditions" when the repo is read-heavy with a single-writer Postgres.

Save pre-analysis report to `<OUTPUT_DIR>/prd_<slug>_repo_analysis.md` BEFORE asking questions. Present to the user in chat as a numbered summary (Portuguese).

### 1.1 Dimension 1: PERFORMANCE implications of the feature
Checklist:
1. What are the repo's hot paths (pages, tRPC routers, DB queries)? Is the proposed feature going to add latency to any of them? Use graphify-out or grep for:
   - Files under `packages/platform/src/app/dashboard/**`, `packages/platform/src/server/api/routers/**`, `packages/db/src/**`
   - Existing N+1 patterns (loops calling `findOne` instead of `findByIds`)
   - Whether the repo uses cache (Redis, Next revalidateTag, db materialized views?)
2. Read-write ratio: count existing endpoints via `grep -c` of mutations vs queries. Is this new feature a write-heavy one? Does it add DB load?
3. Frontend bundle implications: search for existing large lazy-load boundaries, dynamic imports, heavy client-side packages. Will this feature add 100kb+ to the common bundle? (use `package.json` for clues on existing installed libs)

Deliverable: 3 bullets, each with file references + severity: LOW/MEDIUM/HIGH for performance risk.

### 1.2 Dimension 2: SECURITY + PRIVACY implications
Checklist, mapped to the repo's existing patterns (e.g., Flockr has RLS, Supabase Postgres, tRPC with auth ctx):
1. Authentication/authorization: where does this feature fit — public page, logged-in user, organizer/admin role? Look for:
   - `auth()` usage in route handlers / tRPC context
   - `packages/auth/` — session type enum, role checks
   - `packages/db/AGENTS.md` RLS rules (per-worktree)
2. PII exposure: does the new feature display or persist email/phone/DOB/UK postcode? Check existing:
   - Hashing pattern for PII correlation (NOTIFICATION_PII_HASH_SECRET)
   - Logger PII redaction rules
3. Ingestion / external systems: does the feature call Stripe / Resend / Supabase / Linear APIs? Are existing wrapper classes used or raw SDK calls? Search for `new Stripe(`, `resend.emails.send`, `supabase.*` usages.

Deliverable: 3 bullets, evidence, severity. Explicit HIGH if touches PII without existing hashing pattern.

### 1.3 Dimension 3: SCALABILITY + DATA GROWTH implications
Checklist:
1. DB schema growth: if feature adds tables or writes to existing tables → how many rows/event? Estimate 1y volume for UK events (100-500 events/week)? Will we hit Postgres 10M-row warnings in a year?
2. Background jobs: does the feature need async work (webhooks, emails, CSV imports)? Check for existing patterns:
   - Bull / Inngest / cron jobs
   - Stripe webhook handlers in repo
3. Race conditions / idempotency: does the feature involve money (Stripe payment intents, refunds, credits, ticket transfers)? Check existing idempotency key patterns (headers, DB unique constraints).

Deliverable: 3 bullets, evidence. HIGH if money-movement or unbounded data growth.

### 1.4 Dimension 4: MAINTAINABILITY + DEPLOY RISK
Checklist:
1. Codebase architectural pattern: Next.js 13+ App Router (Flockr Lumos uses App Router + RSC)? Where does this feature live: client component, server action, tRPC router, server component?
2. Module boundaries: is it cross-cutting (touching `packages/ui`, `packages/db`, `packages/platform` routers AND pages)? Estimate blast-radius file count based on repo graph. >10 files is a warning.
3. Existing test coverage patterns: Vitest + Playwright? What minimal new tests would the repo expect? Look at existing test: unit files, E2E tests, API route tests. List gaps.

Deliverable: 3 bullets, severity.

### 1.5 Final Repo Analysis Report Summary
Present a final executive table to user before questionnaire begins (Portuguese):

| Dimension | Overall risk | # of HIGH findings | Key files to watch |
|---|---|---|---|
| Performance | LOW/MED/HIGH | k | router A, view B |
| Security / PII | LOW/MED/HIGH | k | auth ctx, packages/db RLX X |
| Scalability / data | LOW/MED/HIGH | k | tables T1, T2 |
| Maintainability | LOW/MED/HIGH | k | cross 5 packages |

This is **NOT negotiable** — show it to the user before asking any feature question.

---

## 2. STEP 2 — ITERATIVE STRUCTURED QUESTIONNAIRE (Mapped to 15 template sections)

Use the PRD_QUESTIONNAIRE_TEMPLATE.md references file.

Ask questions **IN BATCHES of 4-8 questions max per turn**, grouped by the 15 template sections below. WAIT for user answers between each batch (no infinite dump). Iterate: if a user answer is ambiguous or misses the obvious edge case, FOLLOW UP with 1-2 clarifying questions for that line.

Rule for every question:
- Question MUST contain a **repo-grounded hint** ("based on existing pattern at file X, this is how today works...") instead of generic asks.
- Every section that asks for FR/AC/NFR must also prompt for EXPLICIT edge cases (empty state, race, network failure, permission denied, malformed input, idempotent retries).

### Questionnaire Sections (mapped 1-to-1 with template)

Batch 1 (Strategy + Problem):
1. Overview: 1 sentence "what", 1 sentence "why matters".
2. Problem statement: exactly what is broken/missing TODAY? Include a specific user persona + timeline ("as a UK event organizer, when I try to do X during checkout, Y happens and takes 5 min").
3. Goals list: 3-6 S.M.A.R.T goals.
4. Non-goals list: 2-5 things explicitly OUT OF SCOPE for this iteration (VERY IMPORTANT — prevents scope creep later).

Batch 2 (Users + Stories + FRs):
5. User stories table: 3-7 rows. At least: happy path organizer, happy path attendee, admin path, error paths (invalid role).
6. FRs list: FR-1, FR-2, ... (5-12 numbered items). For each: name, triggering event, input, output, 3 edge cases minimum.
7. FR dedup: idempotency / retries / double click prevention.

Batch 3 (NFRs + Data + Systems):
8. NFR table: latency p95 target, availability, data retention (per GDPR for UK? UK GDPR retention periods). Add: Accessibility (WCAG 2.2 AA). Add: PII redaction level. Add: Observability (which events to log — NEVER log PII).
9. Data Model: new/changed tables (use `packages/db/src/entities` existing convention if any). For each column: type + nullable + RLS role access read/write.
10. Migrations: list explicit migration names + description. RLS enable/disable per new table (follow `packages/db/AGENTS.md` rules).
11. System Interactions: list all 3rd-party + internal services. Produce a Mermaid flow/sequence diagram here. For each external call: what's the timeout? Retry policy? Circuit-breaker pattern? Failure mode: degrade gracefully or hard-fail?

Batch 4 (Dedup, Normalisation, AC, Open Qs):
12. Deduplication / update rules: PK match cascade, overwrite vs fill-null-only vs no-op.
13. Normalisation rules: UK address? Money in minor units GBP pence (ALWAYS integer — no floats!). Dates in UTC, display Europe/London. Email lowercase trim. Phone E.164.
14. Acceptance Criteria: 8-20 numbered, testable checkboxes. Include: happy path, role-based permission denied check, invalid input validation 400, concurrent writes (race condition check), webhook retry delivery, accessibility tab order.
15. Open Questions: 5-10 unresolved items. Label each by priority: P0 (blocks implementation) / P1 / P2.

---

## 3. STEP 3 — QUESTIONNAIRE VALIDATION + EXPLICIT EDGE CASE REMINDERS

After ALL questionnaire sections are filled by user, BEFORE writing the PRD:

Run a **critical checklist pass** over all answers and report gaps (if any) to user with numbered warning list. If P0 gap, don't proceed until answered:

Example auto-checks:
- ❌ "User stories não tem papel de attendee ('As a ticket buyer...') — adicionar?" (P0 se público do Flockr é organizers+attendees)
- ❌ "Nenhum AC menciona RLS/Supabase row-level: essa tabela nova tem RLS enable_rls + policies? (Flockr requer RLS em novas tabelas — P0)"
- ❌ "Nenhum FR/NFR menciona moeda em inteiro (GBP pence) — se é feature de pagamento/faturamento, bloqueio (P0)"
- ❌ "Data Model não menciona data retention/GDPR para UK — dados de usuário, retenção default 6 anos contábil ou 12 meses? (P0)"
- ❌ "User stories não tem caso de permission denied (organizador vs admin vs atendente) — obrigatório em ACs (P0)"

If ALL P0 gaps resolved → proceed. If not → loop back to relevant batch section with specific questions.

---

## 4. STEP 4 — PRD ASSEMBLY (Strict 15-section template)

Write the PRD file to the agreed `<output_absolute_path>`.

The format is **VERBATIM** as per the template (15 sections in this exact order):

```
# PRD: [Feature Name]  (1 line, title case, 6w max)
> Linear issue, Status (Draft default), Author, Date
---

## Overview           (1 paragraph)
## Problem Statement  (1 paragraph + 1 bullet example of pain)
## Goals              (3-6 SMART bullets)
## Non-Goals          (2-5 bullets, explicit OOS)
## User Stories       (table As a / I want / So that)
## Functional Requirements  (FR-1..N named; each with edge case sub-bullets)
## Non-Functional Requirements  (table: Requirement / Target; 6-10 rows incl. PII, Accessibility, Observability)
## Data Model         (tables + columns + migration list)
## System Interactions  (flow + Mermaid diagram; failure modes per external call)
## Deduplication / Update Rules  (PK, write semantics, delete)
## Normalisation Rules   (currency GBP pence, UTC tz, E.164, email trim, address)
## Acceptance Criteria   (8-20 numbered checkboxes; include RLS; role-denial; race; malformed)
## Open Questions        (table #/Question/Resolution; P0/P1/P2 labels)
```

If a section is "not applicable" for this feature → write "N/A for this iteration." with a 1-sentence WHY. Never omit a section.

---

## 5. STEP 5 — EXECUTIVE PRD REVIEW (present to user)

After writing PRD to disk, print to chat (Portuguese):

1. **Full absolute path** where it was saved (clickable link).
2. **Summary stats**:
   - Total sections (should be all 15): X / 15
   - FRs: N; ACs: M; NFRs: K; Open Qs: Q (P0: z)
3. **Risk recap from Repo Analysis aligned with PRD**:
   - "Dimension Security: 1 HIGH → mitigado em AC-3 + NFR-4 com RLS + hash PII"
   - etc.
4. **Next steps (choice menu for user)**:
   - (1) Editar seção X (user says which + what text)
   - (2) Preencher Open Questions em batch (user answers P0 first)
   - (3) Mover status Draft → Review + enviar para approval
   - (4) Copiar slug + local para docs/prd se não tiver salvo lá + commit via `/harness-ship`

Wait for user input. Iterate on edits 1 section at a time.

---

## 6. Never-Dos (Critical)

- Never write a PRD BEFORE running the Step 1 repo analysis. Generic PRDs = wasted effort.
- Never write a PRD where a Functional or Acceptance section misses edge cases.
- Never use USD / EUR currency when repo is UK-flavored (Flockr is GBP). Always GBP pence integer in data model sections.
- Never use floats for money. Never.
- Never skip RLS enable line in Data Model migrations for Supabase-backed repos (Flockr). If unsure → add Open Question P0.
- Never log/write to PRD examples with "user@hotmail.com john doe 123 fake st" as if real; use `{role}+tag@example.com` + `+test@example.com` convention.
- Never mark Status as Approved / In Progress unless user EXPLICITLY says "move status to Approved".
