---
name: "harness-code-review"
description: "High-impact code review with TWO MODES: (A) GitHub PR URL as before, or (B) LOCAL WORKTREE MODE when user passes --worktree <path> WITHOUT a GitHub PR URL — reviews files currently in the modification/staging area (git status + git diff). Focuses ONLY on blocking issues: runtime regressions, security/PII leaks, unjustified dependencies, and scope deviations. Invoke when /harness-review is called or user asks for code review."
---

# Harness — Code Review (High Impact Focused)

> **SHARED REFERENCES (CANONICAL — NÃO DUPLICAR corpo aqui):**
> - Security + PII + RLS review checklist: `_shared_checklists/SECURITY_PII_COMMON.md`
> - GitHub CLI gh auth + PR operations: `_shared_checklists/GITHUB_CLI_COMMON.md`

Reviewer role with **two mutually exclusive modes** (choose EXACTLY one):
- **Mode A (Classic)**: Already-opened GitHub Pull Request review via `gh` CLI from PR URL.
- **Mode B (NEW — Local Worktree)**: Local code review of modified/staged files inside a worktree (when user passes `--worktree <path>` or explicitly says "review this worktree" and NO GitHub PR URL was provided).

**Deliberately narrow scope so it's useful without being pedantic.**
We NEVER pick on style, format, naming, Biome warnings (those are CI/lint jobs).
We ONLY flag things that actually break production or waste $$$ or risk users.

---

## 0. Preconditions — Two modes (PICK EXACTLY ONE)

### 0.1 WORKTREE SESSION BINDING CHECK (engineering-contracts §19, NON-NEGOTIABLE, common to BOTH modes)

Run THIS BEFORE deciding mode or starting any review context gathering.

1. **Read Level1 Global Index FIRST:** Read `$HOME/.trae/bindings/registry.jsonl`. Find LAST STATUS=BOUND entry with current SESSION_ID. Use its WORKTREE_ROOT for the session.
2. **Mode B mismatch check (CRITICAL):**
   - If user passed --worktree <path>: confirm Level1 registry WORKTREE_ROOT EXISTS and is DIFFERENT than <path> → BLOCK.
   - Ask: "You asked review on worktree X but Level1 GLOBAL session is BOUND to Y. Options: (A = X, override binding; B = Switch binding switch first; C = Cancel review). NEVER silent override. If no Level1 entry → binding not made; proceed to decision flow to create binding (§19.2 only if user continues."
3. **Mode A PR URL + local worktree:** PR for branch that resides Level 1 registry says BOUND on some worktree:
   - If PR is for branch worktree B user says --worktree pointing to A → BLOCK. Ask which is correct.
4. **Pre-send trimmer refs (global:** Output final report refs file links MUST NOT span ≥2 worktrees unless user explicitly asked cross-worktree comparison. Mixed trim single scope before send.

---

### How to decide which mode
- If user provides **BOTH a GitHub PR URL AND --worktree** → prefer Mode A (PR URL); --worktree becomes optional local path for writing report to disk only.
- If user provides **--worktree <path> (or equivalent explicit worktree indicator) AND NO GitHub PR URL** → **FORCE Mode B (Local Worktree)**. Do NOT ask for a PR URL.

---

### Mode A — GitHub PR URL mode (unchanged classic path)

1. **PR URL** (GitHub). Example: `https://github.com/owner/repo/pull/123`
   - **IMPORTANT**: User rules: when working with GitHub → use `gh` CLI (not browser).
   - Pre-flight: `gh auth status` — if not logged in → guide user to `gh auth login` then stop.
2. **Ticket link OR scope description**:
   - Linear/Jira URL + what the PR is SUPPOSED to do
   - OR plain text description of scope/goals
   - If missing → ASK user for it. Cannot review scope adherence without knowing intended scope.
3. (Optional) Worktree path if user wants local review & fixes right away — otherwise, just review, no local edits.

---

### Mode B — NEW: Local Worktree Modification Area mode (NO GitHub PR URL)

Trigger condition: user passed `--worktree <path>` OR explicitly pointed to a worktree AND did NOT provide any GitHub PR URL.

Preconditions (MANDATORY checks BEFORE starting review):
1. **WORKTREE_ROOT** = absolute path provided by user (e.g. from `--worktree` flag or explicit path).
   - Validate: `cd <WORKTREE_ROOT> && git rev-parse --is-inside-work-tree 2>/dev/null` returns `true`. If not → stop with error "Not a valid git worktree: <path>".
2. **Ticket link OR scope description**:
   - Same requirement as Mode A (Linear/Jira URL or plain text scope/goals).
   - If missing → ASK user for it. Cannot review scope adherence without knowing intended scope.
3. **Modification area non-empty check** (optional warning):
   - Run `cd <WORKTREE_ROOT> && git status --short`
   - If output is EMPTY (zero files modified/staged/deleted/untracked):
     → WARN user "Worktree modification area is empty — there are no changed files to review. Proceed anyway to review full repo against scope? [Y/n]". Wait confirmation. If user says no → stop; if yes → review all touched files from last commit or proceed with user's clarification.

---

## 1. Gather context — Mode-dependent path

### Mode A (GitHub PR) → use gh CLI (no browser)

#### 1.1 PR metadata

```bash
gh pr view <PR_URL> --json \
  number,title,body,state,isDraft,baseRefName,headRefName,additions,deletions,changedFiles,commits,labels,reviewDecision,mergeable,files,author,reviews
```

Record:
- `PR_ID` = number (e.g. 123)
- `BASE_BRANCH`
- `HEAD_BRANCH`
- `changedFiles_count`
- `diff_stat` (additions / deletions)
- Author, labels
- files[] (list of changed files + patches)

#### 1.2 Ticket context

Parse the ticket (Linear/Jira) if provided — via appropriate API (user rules: Linear via GraphQL API, Jira via env vars API). Extract:
- **Goal** da tarefa / acceptance criteria list
- **Out-of-scope** / explicit não-faz
- Arquivos esperados / áreas de risco

If no ticket was given, the user's plain text description becomes the scope of reference.

---

### Mode B (Local Worktree) → use git commands directly (NO gh / NO network)

Run ALL of these inside `<WORKTREE_ROOT>` directory. Never leave the worktree.

#### B-1.1 Capture modified/staged/untracked files + diffs

**Step 1: get full file list (union of staged + unstaged + untracked tracked files).**

```bash
# Summary list (short format — for display + counting):
git status --short

# Individual diffs we need for review (combine BOTH staged + unstaged changes):
#   B-1.1.1: staged diff (files already "git add"ed)
git diff --cached --unified=3

#   B-1.1.2: unstaged diff (working tree modifications not yet added)
git diff --unified=3
```

**Step 2: build the canonical file list `changedFiles[]` we review.**
Rules:
1. Parse `git status --short` output (short format flags: `M` = modified, `A` = added, `D` = deleted, `R` = renamed, `??` = untracked).
2. **Include in review list:**
   - Files with status: `M`, `A`, `R`, `C` (copied), `T` (type changed), `U` (unmerged) — both staged and unstaged variants: ` M` (unstaged only), `M ` (staged only), `MM` (both) → all include.
   - `??` (untracked files): **INCLUDE ONLY if they look like code/config (exts: .ts,.tsx,.js,.jsx,.py,.rs,.go,.java,.kt,.sql,.json,.yaml,.yml,.toml,.md where.md is a PRD/spec doc NOT generic README fluff; if user clarifies include extra, honor that).**
   - Skip binary auto-generated build artifacts (node_modules/, dist/, .next/, build/, coverage/, *.png, *.jpg, *.pdf, *.lock diffs auto-generated by package managers — treat as out-of-scope unless scope says otherwise).
3. **For each file in canonical changedFiles[]:**
   - Record relative path, change type (M/A/D/R/??), count lines added/deleted from its diff block.
   - If file is untracked (`??`) AND new → its "patch" = FULL file content (treat as 100% additions diff block): read it whole via `cat`.
4. Aggregate:
   - `changedFiles_count` = N files in canonical list
   - `diff_stat` = total additions / total deletions (sum from B-1.1.1 + B-1.1.2, excluding skipped binaries/locks)
   - `BASE_BRANCH_HEURISTIC`: run `git rev-parse --abbrev-ref HEAD` → current branch name (for info only — no base/head concept locally; base is assumed to be what's committed on this branch before modifications)

#### B-1.2 Ticket context

Same as Mode A 1.2 — parse ticket (if provided) or use user's plain text scope description.
**CRITICAL for Mode B**: because there's no PR body describing intent locally, the ticket + user scope description becomes the ONLY authority for Category 4 (Scope Deviation) classification. Be conservative.

---

## 1.5 PROJECT CONTEXT BOOTSTRAP — GENÉRICO (OBRIGATÓRIO NEVER-SKIP; roda para BOTH Mode A e Mode B)

> **OBJETIVO:** Antes de OLHAR qualquer finding de diff, absorver as regras, arquitetura e convenções DO PROJETO REAL em que o diff vive. Sem isso, o review só conhece "bom senso genérico" e NÃO PEGA violações de arquitetura do projeto, allowlists route-level, charge-model conventions, regras de RLS locais, etc. Este step é a RAIZ DA DIFERENÇA entre um review superficial 0C/0H e um review que pega 3C/8H bugs de produção. É **NÃO ESPECÍFICO** a nenhum repo — descubra tudo automaticamente por heurísticas de arquivos existentes.

Execute **TODOS** os substeps abaixo. Para cada item: "se o arquivo existir, LEIA-O obrigatoriamente; não pule porque 'já sei' ou 'parece longo'". Nenhum destes arquivos gasta mais que 2–5s de leitura e cada um pode contabilizar por múltiplos findings.

### 1.5.1 Contexto raiz do repositório (TOP-DOWN obrigatórios)

Para cada ARQUIVO ABAIXO no `<WORKTREE_ROOT>` (ou no diretório do repo onde o diff mora):

| # | Arquivo(s) a tentar (se existir, ler INTEIRO) | Por que |
|---|---|---|
| R1 | `AGENTS.md` na raiz do repo | Router de contexto do projeto (pontos a onde estão as regras por área). 99% dos monorepos tem isso. |
| R2 | `CLAUDE.md` na raiz do repo | Contexto para agentes: estrutura de packages, convenções de deploy, comandos por pacote, RLS/DB migration rules. |
| R3 | `README.md` na raiz do repo | Stack usado, como rodar testes, arquitetura high-level (1 passada rápida). |
| R4 | `docs/plan.md` se existir | Fixed constraints do projeto (escopo fechado vs. em aberto). |
| R5 | `docs/decisions.md` ou `docs/adr/` (qualquer `*.md` ADR em ordem alfabética de 5 mais recentes) | Decisões arquiteturais com RATIONALE — saber por que Router→Service→Repository, por que charge-model destination, por que `exports` field strategy. |
| R6 | `graphify-out/GRAPH_REPORT.md` **(se existir)** | Community hubs, file paths para a área do diff — indica a ONDE ler regras específicas (ex: "QR validation está em packages/db + packages/scanner"). |

**Todos R1-R6:** use `Glob(pattern, path=<WORKTREE_ROOT>)` primeiro; para cada que existir → use `Read(file_path)`. Não pule R6 se existir — é um atalho gigante.

### 1.5.2 Rules do projeto (tudo em `.claude/rules/` ou `.agents/rules/`)

1. **Glob todos os arquivos `.md` em:**
   - `<WORKTREE_ROOT>/.claude/rules/*.md` (Caminho Flockr/Lumos e maioria)
   - `<WORKTREE_ROOT>/.agents/rules/*.md` (Caminho alternativo em outros stacks)
2. **Para cada um que existir, LEIA INTEIRO.** Classifique mentalmente em buckets:
   - **Security (ex: `security.md`)** — authz inside each action, cookie vs. membership validation, RLS defaults.
   - **Architecture (ex: `architecture.md`, `data-layer.md`)** — Router→Service→Repository layering, "Nenhuma business logic em routers/procedures", Repositories own all TypeORM querying.
   - **Database (ex: `db.md`, `migrations-*.md`)** — Never hand-create migration files, timestamps fabricados, consolidation pre-merge, RLS policies com explicit TO role.
   - **Market/TZ (ex: `uk-market.md`)** — Store UTC / display Europe/London, currency GBP integer minor units.
   - **Frontend/React (ex: `react.md`)** — useTransition rules, error.code vs substring match.
   - **Other (workflow.md, commits.md, tooling.md, testing.md, db-caching.md)** — Pool ceilings PgBouncer, authzCache 4th arg threading rules, idempotency patterns.
3. **Resumo mental OBRIGATÓRIO de 1 frase por bucket após a leitura**: ex "Security = org check não pode ser só cookie raw, Architecture = routers só authz+validate+call svc, DB = migration timestamps fabricados viola rule".

### 1.5.3 Pacotes / Módulos AFETADOS pelo diff (contexto BOTTOM-UP)

1. **Compute `affected_areas`** — do `changedFiles[]` (B-1.1), extraia os paths de topo-level package/app:
   - Ex: `packages/platform/server/api/routers/bookingRouter.ts` → afeta `packages/platform` + `packages/db` (se tabela nova) + `packages/notification` (se email)
   - Ex: `apps/backend/src/webhooks/stripe/route.ts` → afeta `apps/backend`
2. **Para CADA package/app em `affected_areas`, LEIA (se existir):**
   - `<package_path>/AGENTS.md` (package-level rules — critical!)
   - `<package_path>/CLAUDE.md` (diretório map, comandos do package)
   - `<package_path>/README.md` (se existir)
   - **Docs area relacionados:** se `affected_areas` includes `packages/platform` → ler `docs/platform.md` (payment flow, routers structure); se `packages/scanner` → `docs/scanner.md`; se db/entities → `docs/packages.md`. Use Glob `docs/*.md` e leia os matches.
3. **Regra OBRIGATÓRIA para cross-file pipeline integrity (MESMORAM se não tiver doc):**
   - Se diff tocar QUALQUER handler/service de webhook (`webhook`, `Webhook*`, `api/webhooks/*/route.ts`, `supportedTypes`): **LEIA AGORA O(S) ARQUIVO(S) ROUTE-LEVEL dispatcher** e compare com service supported types — mesmo que nenhuma doc diga para fazer.
   - Se diff tocar PSP/Connect charges/refunds/transfers: **LEIA AGORA os arquivos de createPaymentIntent/createRefund/todas as chamadas que tocam o cliente PSP no mesmo package** — mesmo que não tenha doc.

### 1.5.4 Se existir skill de review LOCAL DO PROJETO, absorva seus checks

1. **Glob para skills locais no projeto:**
   - `<WORKTREE_ROOT>/.claude/skills/*/SKILL.md`
   - `<WORKTREE_ROOT>/.agents/skills/*/SKILL.md`
2. **Para cada skill cujo nome case com review/code-review/audit (ex: `flockr-review/SKILL.md`, `project-review/SKILL.md`):**
   - LEIA INTEIRO.
   - **Extraia sua checklist de "o que checar em Step 3 / Step Review".** INCORPORE esses checks NO SEU framework de Category 0/1/2/3/4 (adicione checks como sub-itens OBRIGATÓRIOS durante a avaliação — não ignore-os por ser "skill diferente").
   - Se a skill local listar caminhos de arquivos ESPECÍFICOS para ler (ex: "ler route.ts no webhook stripe"), **LEIA-OS AGORA MESMO** — antes de começar o review framework. Não finja que já leu.

### 1.5.5 Checklist de confirmação de bootstrap (NÃO passe adiante sem marcar TODOS)

Antes de entrar no §2 Review Framework — responda estas perguntas SILENCIOSAMENTE para você mesmo. Se QUALQUER UMA for NÃO, volte e leia.

```
[ ] R1-R6 raiz lidos (todos que existiam)
[ ] .claude/rules/*.md ou .agents/rules/*.md TODOS lidos (todos que existiam)
[ ] affected_areas packages: AGENTS.md e CLAUDE.md lidos
[ ] docs/*.md relevantes (platform/scanner/packages/decisions) lidos se existiam
[ ] graphify-out/GRAPH_REPORT.md lido se existia
[ ] skill local <projeto>-review/SKILL.md lida e checks absorvidos (se existia)
[ ] diff toca webhooks? SIM → route-level allowlist file JÁ LIDO, não só service
[ ] diff toca PSP/Connect charges/refunds/transfers? SIM → TODAS as chamadas psp no mesmo package JÁ LIDAS, não só o diff hunk
```

---

## 2. Review framework — 5 categories ONLY

We only look at these 5. Anything else is out-of-scope for this reviewer role.

---

### Category 0: 🔴 Cross-File Pipeline Integrity Checks (CRITICAL or HIGH; never skip)

These are "diff looks fine, but entry point upstream dropped it" bugs that unit/E2E tests miss because tests call services directly. Run EVERY subheading below — if the diff touches ANY of the keywords mentioned, you MUST do the cross-file read.

#### 0.1 Webhook pipeline entrypoint allowlist vs service handlers (CRITICAL if mismatch)
If diff touches files with `webhook`, `Webhook*Service`, `supportedTypes`, `handleStripe*`, `charge.`, `customer.`, `route.ts` under `api/webhooks/`:

1. Read the **ROUTE-level allowlist** (early arrays like `stripeSnapshotEventTypes`, `acceptedEvents` at the TOP of `/api/webhooks/*/route.ts` or dispatcher functions).
2. Read the **service handler's supported events** (e.g. `WebhookService.supportedTypes`, switch-cases inside `handleEvent`).
3. **CRITICAL if:**
   - Service handles an event type that is NOT in the route-level allowlist.
   - Route returns `202 / ignored: true` / drops events that the service actually needs.
   - Note: tests calling `svc.handleEvent()` directly BYPASS this check — inspect the real route file, not the test.
4. Fix: add missing type to allowlist + require a signed-payload route-level POST test.

#### 0.2 Connect / PSP charge-model consistency (CRITICAL if contradiction)
If diff touches `createPaymentIntent`, `createRefund`, `transfer`, `reverse_transfer`, `stripeAccount`, `transfer_data.destination`, `on_behalf_of`, `application_fee_amount` or equivalent PSP params:

> **PROCEDIMENTO OBRIGATÓRIO 3-PASS — NÃO PULE nenhum:**
> 
> **Passo 1 (extrair params de createPaymentIntent):**
> Ache a linha onde `paymentIntents.create(...)` / `createPaymentIntent(...)` é chamada.
> - (a) 2º argumento (headers): existe `{ stripeAccount: X }` (ou similar `stripeAccount` header)? Anote `X` = valor exato (ex: `payload.stripeConnectedAccountId`, uma variável).
> - (b) 1º argumento (body params): existe objeto `transfer_data: { destination: Y }` (ou `transfer_data.destination = Y`)? Anote `Y` = valor exato.
> 
> **Passo 2 (detectar contradição createPaymentIntent):**
> SE (a) E (b) são AMBOS verdadeiros → compare `X` e `Y`.
> - **CRITICAL se `X === Y`** (destino = mesma conta que está emitindo o request). Motivo: Stripe rejeita com HTTP 400 `transfer_data[destination]` cannot equal the account making the request → TODO Connect checkout falha.
> 
> **Passo 3 (cross-check createPaymentIntent model vs createRefund model):**
> Após classificar createPaymentIntent como DESTINATION CHARGE (apenas (b), sem (a)) ou DIRECT CHARGE (apenas (a), sem (b)), agora ache `createRefund(...)` ou `refunds.create(...)`:
> - (r1) existe `stripeAccount` header?
> - (r2) existe `reverse_transfer: true`?
> - **CRITICAL se createPaymentIntent = DESTINATION CHARGE (platform cria) E createRefund usa stripeAccount connected + reverse_transfer: true**. Motivo: `reverse_transfer` só funciona em refunds emitidos DO PLATFORM (stripeAccount não setado). createRefund com stripeAccount connectedAccountId vai procurar o charge/pi dentro da connected account — mas destination-charge PIs vivem na PLATFORM account → wrong namespace. Stripe não acha → 404.
> - **CRITICAL se createPaymentIntent = DIRECT CHARGE (stripeAccount=X) E createRefund NÃO TEM stripeAccount=X E TEM reverse_transfer=true**. Motivo: direct charge não teve nenhum transfer_data para reverter; refund vem da connected account, mas o request sem stripeAccount cai na platform account → 404 charge not found.

1. Classify formally (after running the 3-pass above):
   - **Destination charge model:** payment intent created ON platform account (no `stripeAccount` param on create); `transfer_data.destination=connected`, `application_fee_amount`, `on_behalf_of` present. Refunds issued from platform with `reverse_transfer: true`.
   - **Direct charge model:** payment intent created WITH `{ stripeAccount: connectedAccountId }` header; NO `transfer_data.destination` (PSP rejects if equal to requester); refund issued with same `stripeAccount` header.
2. **CRITICAL if (after 3-pass):** any method mixes models. Examples:
   - `createPaymentIntent` issued with `stripeAccount` (direct) but still carries `transfer_data.destination = same account` → request fails.
   - `createRefund` issued with `stripeAccount:` header AND `reverse_transfer: true` → reverse_transfer only applies to destination-charge model; wrong ID namespace if PI lives on platform account.
3. Fix: pick one model end-to-end; keep refunds/PIs consistent. Mock clients mask this — READ the real client parameterization.

#### 0.3 Transaction + row lock duration vs network calls (HIGH if overlap)
If the diff contains BOTH (a) transaction/lock primitives AND (b) external network awaitables:
- (a) signals: `queryRunner.startTransaction()`, `manager.transaction()`, `setLock("pessimistic_write")`, `lockForUpdate`, `FOR UPDATE`, `BEGIN`;
- (b) signals: `await stripe.*`, `await fetch`, `await mailer.send`, `await new Promise(...setTimeout...)`, retry/backoff sleeps.

1. Trace the span: `tx start → [await network call(s) with backoff?] → tx commit/rollback`.
2. **HIGH if:** any external network await with backoff falls inside that span. Reason: pool ceilings (e.g. ≤10 PgBouncer sessions) → under modest concurrency this risks DB-connection-exhaustion 500s across the whole app.
3. Fix: 2-phase — short tx #1 writes PROCESSING/idempotency claim + commits; network call outside any tx; short tx #2 applies side effects / marks failed.

#### 0.4 Serverless fire-and-forget post-response work (HIGH if non-waited)
If diff contains `void (async () => ...)();` or `setImmediate(async ...)` or `setTimeout(async ...)` wrapping:
- outbound emails (mailer.send / notification adapter),
- analytics/ETL upserts (sales_by_date, aggregator ON CONFLICT writes),
- event publishes / logger flushes.

1. Does the HTTP/tRPC return BEFORE those tasks are awaited?
2. **HIGH if yes.** Reasoning: Vercel/Next serverless may freeze at response; work silently lost. In-process E2E tests pass because they wait 30ms after return — that does not reflect prod.
3. Fix: `waitUntil` (`@vercel/functions` / `Next after()`) or await before return; add route-level test that post-response work happened.

---

### Category 1: 🔴 Runtime breakage / silent incorrect behavior (CRITICAL if found)

What counts (Category 0 + 1 together = CRITICAL or HIGH runtime):
- **Possible NullPointer / undefined field dereference** at runtime (access `obj.field.subfield` where `obj.field` can be null/undefined based on the types / DB schema and there's no guard).
- **Race conditions**: async operations with TOCTOU, unhandled Promise rejections, missing `await` on async functions, `Promise.all()` where one fails silently, race on shared mutable state.
- **Wrong algorithm / calculation**: obvious logic errors (if/else swapped, `<=` should be `<`, `+` should be `-`, currency divided by 100 twice so $1.00 becomes $0.01).
- **Schema backwards-incompatible change**: API returns a type that old clients can't handle.
- **Deprecation wrong API usage**: calling a deprecated endpoint / method that the upstream docs say will fail (e.g. Stripe v1 endpoint in a v2-only integration).
- **Missing null/empty handling**: DB returns `[]` for an "empty list" vs `null` for "not queried" and code treats both the same way when they shouldn't be.
- **Boundary conditions**: off-by-one, array index `-1`, pagination last page truncated, decimal precision loss in currency fields (float `0.1 + 0.2` for money — MUST use integer cents or Decimal types).
- **Unverified type cast**: `as T` in TS without runtime validation guard; data from API/DB/JSON assumed typed but never checked.
- **PSP charge/version assumptions**: handler reads nested fields (e.g. `charge.refunds.data[0]`) whose presence depends on API version / expansion; no undefined-check → silently drops event. (Also cross-check with 0.2.)
- **Timezone incorrectness**: stored-local times treated as UTC in comparisons (e.g. BST vs UTC makes "event started" gates ±1h wrong). MEDIUM if gated; HIGH if gates are user-visible eligibility for refund/cancel.
- **Row multiplication + LIMIT 1 queries**: LEFT JOIN 1:N relations (items/inventories/events/org accounts) + LIMIT 1 returns arbitrary row → wrong org/event/time used in gates. HIGH if money or security gate; else MEDIUM.
- **null-cast quirks in ORM find-options**: `null as unknown as undefined` where explicit IsNull() should be used. MEDIUM default; promote HIGH if the field is part of idempotency/composite PK matching.
- **Crash-safety "PROCESSING first" writes inside same transaction as external await (MEDIUM/HIGH — ligado a Category 0.3)**. Se uma DB transaction escreve a row PROCESSING (claim/idempotency) e faz `startTransaction()` → escreve PROCESSING → depois `await stripe_network_call` → depois `commit`. Qualquer crash ou rollback no meio vai APAGAR a PROCESSING row junto (transaction never committed). Resultado: "estado intermediário PROCESSING nunca sobrevive a falha" e catch block que dá `markFailed` na row vira dead code (row não existe mais). **MEDIUM se também tem o pattern Category 0.3 HIGH.** Fix: Category 0.3 2-phase pattern resolve automaticamente — Tx1 escreve e COMMITA a PROCESSING row ANTES de qualquer network call.
- **Error message substring match brittle vs error.code enum match (LOW/MEDIUM)**. Handler/caller lida com erros checando `e.message.includes("already been used/scanned")` em vez de `(e as RefundValidationError).code === "TICKET_ALREADY_SCANNED"`. MEDIUM se o error kind vem de service boundary. LOW se só logging.
- **Circular imports via cross-import error classes/services (LOW/MEDIUM)**. Service A importa `SomeError` de Service B file, Service B importa symbols de Service A file → resultado: circular import chain. MEDIUM se isso causa runtime undefined (TypeScript strict mode levantará warning). Fix: mover error classes/enums compartilhados para módulo dedicado `domain/errors.ts` / `server/domain/refundErrors.ts`.
- **Entity decorator index names vs migration index names DRIFT (LOW/MEDIUM)**. TypeORM entity `@Index("idx_refunds_stripe_refund_id", { unique: true })` decorator mas migration CREATE TABLE cria `uq_refunds_stripe_refund_id` (nome diferente), ou entity @Index() sem nome mas migration nomeia `idx_refunds_org_id`. Resultado: próximo `migration:generate` emitirá spurious DROP/CREATE churn sem mudança real. MEDIUM se >2 name mismatches.
- **Idempotency find-options match de NULL via double cast `null as unknown as undefined` → HIGH if idempotency/composite PK (ja listado acima)**.

Each entry: CRITICAL severity unless provably unreachable path.

---

### Category 2: 🔴 Security / PII / Compliance (CRITICAL or HIGH)

Reuse **harness-compliance** skill categories — but applied to the PR DIFF only (light scan equivalent). PLUS the new cross-file authz audits below (2.8–2.10) which are MANDATORY if any diff file touches org-scoped handlers, authz calls, or Stripe Connect.

Checks:
1. **Secrets/credentials** hardcoded: Stripe `sk_*`, GitHub PAT, AWS AKIA, private keys, API keys in env vars printed. CRITICAL.
2. **Raw PII logging**: `console.log(email)`, logger with unhashed `phone`. CRITICAL or HIGH depending on context (dev log vs prod persistent log).
3. **SQL injection**: string-concatenated SQL, `.raw()` / `.whereRaw` with no parameterized array. HIGH usually, CRITICAL if user input flows unfiltered.
4. **XSS / SSRF**: `dangerouslySetInnerHTML` without sanitization; user-controlled `fetch(url)` without hostname whitelist. HIGH.
5. **Auth/RLS bypass**: endpoint missing auth guard; server action checking role AFTER the DB write; service_role key used on client. CRITICAL.
6. **Destructive operations + missing guardrails**: DROP TABLE / TRUNCATE without `NODE_ENV !== 'production'` check; `fs.rm(force:true recursive:true)` with user-supplied path.
7. **Dangerous URLs**: new DB URLs pointing to production-looking hosts (`*.rds.amazonaws.com`, `*.supabase.co`, `*.neon.tech`) — flag HIGH, require confirmation.
8. **MANDATORY cross-file — raw cookie org check vs membership-validated context (CRITICAL/HIGH depending on procedure path)**. NÃO AGREGUE RESULTADOS DE UM PROCEDURE NOS OUTROS — analise cada procedure SEPARADAMENTE.
   - **Primeiro**: Liste TODOS os procedures/handlers NOVOS ou MODIFICADOS no router (ex: bookingRouter.ts tem `refundOrder` mutation + `getEligibleForRefund` query + `getBookingRefundStatus` query → 3 procedures = 3 auditorias INDEPENDENTES).
   - **Para CADA procedure (tanto READ quanto WRITE)**: se o corpo do handler usa `ctx.activeOrgId` / `ctxOrgId` / `active_org` cookie value para fazer gating com uma `row.org_id` (ex: `if (ctxOrgId && refundContext.orgId !== ctxOrgId) throw Forbidden`):
     1. Trace a origem de `ctx.activeOrgId`. Muitas vezes é `active_org` cookie raw — procure em `server/trpc.ts`, `server/context.ts` ~ linhas 30–60.
     2. Procure por re-validação de membership: existe chamada a `authzService.assertCan(ctx.userId, "org:read"|"org:manage", {type:"org", orgId: rowOrgId}, ctx.authzCache)` OU `OrgContextService.getWhoAmI(userId, activeOrgSignal)` OU query de membership no banco que confirme `user ∈ org` ANTES do gating?
     3. O buyer fallback path (ex: `if (row.userId === ctx.userId) permitido`) é aceitável e mitiga reads de buyer-owned data.
   - **Severity por procedure**:
     - **CRITICAL se** é um procedure **READ** (query `getEligibility`, `getStatus`, detail view) e o gating é SOMENTE cookie↔row comparison SEM membership validada (sem assertCan/whoami). Motivo: qualquer usuário autenticado seta o cookie → lê dados cross-org de pagamentos/stripe_refund_id/valores/compradores.
     - **HIGH se** é um procedure **WRITE** (mutation `refundOrder`, `cancelBooking`) e o gating é cookie↔row SEM membership validada, MAS há downstream guards (DB order locked + authz.assertCan com orderCtx.orgId da row) como mitigação.
     - **LOW/NÃO FLAG** apenas se (a) assertCan é chamado ANTES do gating COM a orgId da row (não do cookie), OU (b) whoami revalidou membership, OU (c) todo acesso passa por buyer fallback path (row.userId === ctx.userId) sem possibilidade de cross-org read.
9. **MANDATORY — authzService.assertCan 4th arg authzCache threading (HIGH if missing in router-callable service paths)**. If the diff contains `.assertCan(userId, permission, resource)`: read its signature — does it accept `cache?: AuthzCache` as a 4th optional param? Does a router ctx expose `ctx.authzCache`? Trace service-layer params from router → service. Flag HIGH if services reachable from routers call assertCan WITHOUT passing a cache, because otherwise each call issues a fresh isPlatformAdmin DB query (N+1 per router call under default db-caching rule).
10. **Server action / route handler auth ordering (CRITICAL if after writes)**. Authz checks run INSIDE the endpoint (per security rule); they must run BEFORE any DB write or side effect. CRITICAL if order is reversed.

---

### Category 3: 🟠 Architecture / Backend Layering & Repository Boundary Violations + Migration Hygiene (HIGH or MEDIUM)

Checks:
1. **Router layering — NO business logic + NO direct repository instantiation inside procedures (HIGH/MEDIUM)**.
   - **Primeiro (obrigatório)**: Liste TODOS os procedures/handlers NOVOS/MODIFICADOS no router file (ex: bookingRouter → 3 procedures).
   - **Para CADA procedure (HIGH se violar)**:
     - (a) Conta linhas do corpo interno do handler (não conta a linha de declaração do procedure). Se `> 50 linhas` → suspeito de violação Router→Service→Repository.
     - (b) Procura por instantiation de repositórios DENTRO do router file: `new OrderRepository(...)`, `new RefundRepository(...)`, ou imports de arquivos repository e chamadas diretas `.findById(...)` / `.getRefundContext(...)` / `.findByPaymentId(...)` SEM passar por um Service. Qualquer uso direto de repository methods no router → **HIGH severity violation** (architecture.md: "Routers must not own data access").
     - (c) Procura por arithmetic/window/refund-gate inline: `15_552_000_000` (ms constants), partial-refund detection, `scannedCount > 0` gates, `if (eventStartAt <= Date.now())` event-past gates, `180*24*60*60*1000` constants hardcoded. E existe um Service correspondente com os mesmos gates (mesmo que usando outra constante com mesmo valor) → **HIGH drift risk**.
     - (d) Se só tem inline calculations (sem direct repo instantiation) e não tem service equivalente → **MEDIUM**.
   - Fix: router procedure = 3 linhas máximo: `validate input` → `authorize assertCan(...)` → `call service.someMethod(...)`. Methods de service retornam structs que o router só repassa como response.
2. **Repository-layer bypass writes inside services (HIGH for writes; MEDIUM for reads)**. If diff contains `queryRunner.manager.getRepository(X).update/.insert/.delete`, or raw `.createQueryBuilder(...).execute()` writes inside a service file (not a repository file). Architecture rule: "Repositories own all TypeORM querying". HIGH if writes (breaks the atomic DB schema surface); MEDIUM if read-only queries.
3. **Entity/enum definitions inside apps** (data-layer.md rules). Flag HIGH if apps define TypeORM entities / duplicate enums / own migration runners. All come from `@flockr/db` shared package.
4. **Migration Hygiene — hand-created fabricated timestamps + intra-branch consolidation + RLS policy defaults (HIGH/MEDIUM)**. Se `changedFiles[]` contiver quaisquer arquivos em paths `**/migrations/*.ts` / `**/migrations/*.sql` / `**/db/migrations/*`:
   - **(a) Fabricated timestamps (HIGH)**: Extraia o prefixo numérico (geralmente 13 dígitos ms UNIX) de CADA migration filename (ex: `1788150000000-CreateRefundsTable.ts`, `1788150001000-AddPaymentsRefundId.ts`). SE múltiplas migrations no mesmo branch tem timestamps REDONDOS / IGUAIS NO ÚLTIMO 3-4 DÍGITOS / espaçamento EXATO entre si (ex: 1000ms, 10_000ms) → **HIGH**. Motivo: `migration:create` CLI gera timestamps de tempo real (aleatórios nos últimos dígitos). Timestamps redondos/arredondados = arquivo criado à mão → viola packages/db rule "Never hand-create migration files".
   - **(b) Intra-branch patching (HIGH)**: Uma migration M-1 cria um enum tipo X (ex: `CREATE TYPE refund_status_enum AS ENUM (PENDING,COMPLETED,FAILED)`), e OUTRA migration M-2/M-3/... DENTRO DO MESMO BRANCH (mesmo diff) ALTERA esse mesmo enum com `ALTER TYPE ... ADD VALUE` ou DROP + RECREATE → **HIGH**. Motivo: pré-merge, branch migrations DEVEM ser consolidadas em 1 migration end-state (não 5 patches seguidos).
   - **(c) RLS policy TO PUBLIC default + grants inconsistentes (MEDIUM)**: Nas migrations SQL olhe políticas de RLS: `CREATE POLICY name ON table ...` SEM cláusula `TO authenticated`/`TO service_role` (implica `TO PUBLIC`). Olhe também `GRANT ...`: e política é INSERT mas só `GRANT SELECT` foi dado (policy fica inerte para client roles). **MEDIUM severity**.
5. **New npm/cargo/pip dependency added to package.json/Cargo.toml/requirements.txt/go.mod** AND:
   - It wasn't mentioned in the ticket/scope
   - There's NO justification comment in the PR body
   - A cursory repo search shows a similar helper/function/module already exists
6. **PR with >30 files changed** WITHOUT a clear justification in the PR description why this can't be split into 2+ smaller PRs. (Flag as MEDIUM risk — harder to review, higher chance of hidden bugs.)
7. **File added outside the module area** that the scope was supposed to touch — scope creep indicator.

---

### Category 4: 🟠 Scope deviation / UI demo vs claimed wiring (MEDIUM — blocking per user spec)

How:
1. Take scope description / ticket ACs.
2. For each file changed: classify what that file implements.
3. Compare:
   - **Missing from PR** = ACs not implemented → CRITICAL/HIGH depending on severity
   - **Added to PR but never mentioned** = scope creep → MEDIUM severity, must justify; user explicitly asked us to flag this.
   - Examples:
     - Ticket = "fix login 500" → PR also adds "new forgot password feature" → SCOPE CREEP, flag MEDIUM.
     - Ticket = "add event search" → PR skips the pagination AC mentioned → MISSING, flag HIGH.
4. **UI demo simulation vs misleading commit/AC claim (HIGH if mismatch)**.
   - **Primeiro (obrigatório)**: Liste TODOS arquivos `.tsx` NOVOS no diff, especialmente aqueles com nome matchando a feature do ticket (ex: ticket "Process a refund" → arquivos `*Refund*Action.tsx`, `*Refund*Dialog.tsx`, `*BookingRefund*.tsx`). Para CADA um, rode o **PROCEDIMENTO 5-PASS NÃO-PULE** abaixo:
   - **Passo A — Fake latency scan**: regex match `/setTimeout\s*\(\s*r\s*=>\s*\{?\s*\}|await\s+new\s+Promise\s*\(\s*(?:r|resolve)\s*=>\s*.*setTimeout|sleep\s*\(\s*1\d{3}\s*\)/` no body do componente. Se match → A = YES.
   - **Passo B — Simulated failure scan**: regex match `/Math\.random\s*\(\s*\)\s*<\s*0\.\d+/` (ex: `Math.random() < 0.1`). Se match → B = YES.
   - **Passo C — Discarded generated key scan**: regex match `/void\s+(?:idempotencyKey|uuid|key|nonce|generatedKey)\s*[;,]/` ou variável gerada com `crypto.randomUUID()` / `ulid()` / `nanoid()` e nunca usada em parâmetro de chamada API. Se match → C = YES.
   - **Passo D — Toast success/fail SEM backend call**: Procure por `toast.success(` ou `toast.error(` ou `toast.info(`. ACIMA dessa linha (dentro de 10 linhas) existe chamada a `api.xxx.useMutation` / `mutate(` / `mutateAsync(` / `fetch(` / `axios.post(` / `trpcClient.xxx(` com endpoint real? SE toasts aparecem SEM que NENHUMA chamada a backend exista no handler → D = YES.
   - **Passo E — Demo data source scan**: Procure por imports `/demoBookings|demo-data|mock-data|seed-demo/` no topo do componente, ou variáveis nomeadas `demoXXX`, `mockXXX` usadas como data source (não como test fixtures). Se match → E = YES.
   - **Severity check**: SE (A OU B OU C OU D) for YES **E** (commit message / PR title / ticket ACs dizem que a feature é "wired to backend" / "complete UI integration" / não diz "demo" ou "scaffold") → **HIGH severity finding**. Motivo: commit misleading faz reviewer/PM achar que feature está integrada, mas é fake.
   - Fix: OU (1) wire o handler corretamente: chamar o tRPC mutation com o idempotencyKey gerado, gate visibility com getEligibility/service call, ou (2) prominentemente label o componente como DEMO e separar de shipping code path (ex: mover para `components/demo/*` + comentário `// TODO REMOVE BEFORE SHIP` no topo).
5. **4.7 Test-suite naming behavioral check (REGRA 7.9 do harness, MEDIUM / WARN).**

   Scan test files added/modified in the diff (`*.test.*`, `*.spec.*`, files inside `__tests__/`). Detect anti-patterns **in the TITLE STRING** of `describe("...")` / `it("...")` / `test("...")`:
   - Ticket IDs: `FLO-\d+`, ticket-codes like `ABC-123`
   - Task/item IDs: `Task? T\d+(\.\d+)?`, `Item \d+`
   - AC/section IDs: `AC\d+`, `§\d+(\.\d+)?`, `REGRA \d+`, `SPEC_XXX`, `PRD §`
   - Phase/story IDs: `Fase \d+`, `Story #?\d+`

   Severity:
   - 1–4 bad titles → **LOW WARN** (non-blocking, show in "Nice-to-have" list)
   - 5–9 bad titles → **MEDIUM** (appear in main findings; require rename before merge or explicit override comment)
   - ≥10 bad titles → **HIGH** (blocking: relatório de CI vai ser inútil, alguém quebra essa regra em escala)

   Never flag the JSDoc traceability comment ABOVE a block or a `// @ac X | @task Y | @ticket Z` line INSIDE the block as bad. Those are the RECOMMENDED way to keep traceability without polluting the display title.
6. **4.8 Route-level / failure-path test gap check (MEDIUM if missing)**. If Category 0 found a new webhook route event type → require 1 route-level signed-payload POST test (not just svc.handleEvent direct). If Category 0.3 flagged a tx pattern → require 1 failure path test: Stripe 5xx → tx rolls back + retry with same idempotency key → no double-effect. MEDIUM severity (waivable only with PR body sign-off override).

---

## 3. NON-goals (we explicitly skip these — do NOT waste tokens / time)

- ❌ Biome / formatting / indentation issues. (That's lint CI.)
- ❌ Naming nitpicks: `myVar` vs `my_variable`, component naming casing. **EXCEÇÃO:** naming of test-suite `describe()` / `it()` / `test()` titles, which falls under Category 4.7 (REGRA 7.9 behavioral check), reviewed above.
- ❌ Test coverage% alone (we check if tests MISS for CRITICAL code but won't demand lines).
- ❌ Documentation README unless it's actively misleading about security/usage.
- ❌ TODO/FIXME comments (unless for auth/security debt).
- ❌ General refactors that don't risk correctness.

---

## 4. Output — Structured Review Report (English for files/code refs, PT for user narrative)

Follow template: `references/REVIEW_REPORT_TEMPLATE.md`

**MANDATORY SECTIONS ORDER (do NOT skip any):**

**1. Header (mode-dependent):**
- Mode A (PR URL): Write a first line `# Review Report — PR #<PR_ID>: <title>`
- Mode B (Worktree Local): Write `# Review Report — LOCAL WORKTREE MODE` then `## Context` with subfields:
  - Worktree path: `<WORKTREE_ROOT>`
  - Current branch: `<BASE_BRANCH_HEURISTIC>`
  - Changed files count: `<changedFiles_count>`
  - Diff stat: `<+additions / -deletions>`
  - Changed files list (table: Status | Path | +/- lines)

**2. Executive Verdict** (template section — não saltar):
- 🔴 Request changes (≥1 CRITICAL or ≥2 HIGH) / 🟡 Approve with comments / 🟢 Approve
- Blocker tally table: CRITICAL / HIGH / MEDIUM / LOW — counts

**3. Context Bootstrap Evidence TABLE** (OBRIGATÓRIO — nunca empty):
- Preencha a tabela do template. Cada item §1.5 (R1-R6, rules, packages afetados, skill local absorbed, cross-file pipeline reads). Se não existir arquivo = escrever "(N/A — arquivo inexistente no repositório)". NÃO deixe linha em branco.

**4. Findings section:**

For each finding (both modes identical from here):
- Severity: 🔴 CRITICAL / 🟠 HIGH / 🟡 MEDIUM / LOW WARN NON-BLOCKING
- Category: Pipeline Integrity / Runtime / Security / Architecture / Scope
- File:line
- Snippet (3 lines before + 3 lines after, from patch)
- Why this is a problem (evidence-based — never "I don't like it")
- **Explicit rule citation (MANDATORY when possible)**: quote the EXACT project rule file:line from .claude/rules/*.md / AGENTS.md / decision docs you read during bootstrap. Example: "viola [architecture.md](file:///.../.claude/rules/architecture.md#L12) 'Router → Service → Repository: Routers must not contain business logic >30 lines'".
- Actionable fix — specific lines/what should replace
- Optional: suggest code change snippet ONLY if obvious. NEVER rewrite whole file.

**N-1. Coverage of Review TABLE** (OBRIGATÓRIO — usuário confia audit):
- 6 rows obrigatórias: §1.5 Bootstrap → Category 0 Pipeline Integrity → Category 1 Runtime → Category 2 Security+PII+Authz audit → Category 3 Architecture/Repo boundary → Category 4 Scope deviation / Demo UI / Test naming
- Non-goals (style/format/coverage%) → Skipped intentionally note.

**N. Final verdict section (template):**

Then at the end (both modes, except verdict notes):
- **Verdict**: 🔴 Request changes (≥1 CRITICAL or ≥2 HIGH) / 🟡 Approve with comments (only MEDIUMs/LOWs) / 🟢 Approve
  - **Mode B NOTE**: Verdict labels above refer to "if this were submitted as a PR". Since it's local work-in-progress, interpret as: 🔴 = Fix these before committing/pushing; 🟡 = Fix before merging; 🟢 = Clean.
- **Blocker summary**: numbered list — each CRITICAL/HIGH must be fixed before merge (or before commit+push in Mode B)
- **Non-blocker nice-to-have**: numbered list — MEDIUM/LOW, fix or ignore, user decides

---

## 5. Post-report actions

### Mode A (GitHub PR) — unchanged:
- Write review report TO DISK at:
  `$HARNESS_SESSION_DIR/reports/review_PR-<ID>_<YYYYMMDD>.md` (EFÊMERO per-session, via contract)
  (If no worktree / binding exists yet, fallback: write report to chat + offer to save at user home `~/.trae/reports/`.)
- **DO NOT approve or request changes DIRECTLY on GitHub via `gh pr review`** unless user explicitly asks after seeing the report and saying "suba isso como review oficial". Our first deliverable = the report for the user to review in chat.
- If there are ZERO findings → still write a report saying "No CRITICAL/HIGH issues found; scope matches; dependencies justified." + list what you checked so user trusts the review was actually done.

### Mode B (Local Worktree) — NEW:
- Write review report TO DISK at:
  `$HARNESS_SESSION_DIR/reports/review_LOCAL-WORKTREE_<YYYYMMDD>_<HHMMSS>.md` (EFÊMERO per-session, via contract)
  (Timestamped because there may be multiple local review passes before code is committed.)
- **DO NOT interact with GitHub at all** in Mode B (no gh commands, no PR creation). Pure local output only.
- Zero findings → still write report with: "No CRITICAL/HIGH issues found in modified files. Scope matches stated goals; dependencies justified." Include the full changed files list + what you checked per category (Runtime/Security/Deps/Scope) so user trusts audit was actually done.
- Optional user convenience at end of chat message:
  - If Mode B, after presenting findings, offer ONE follow-up action:
    - `[Apply fixes locally]` — if user says yes, proceed using harness-developer mindset to fix the CRITICAL/HIGH blockers inside the same worktree (still under scope; don't add features).
    - `[Show just the blocked items condensed]` — for brevity.
    - `[Nothing, thanks]` — stop.
  Don't be pushy. If user just says "ok thanks" → stop.
