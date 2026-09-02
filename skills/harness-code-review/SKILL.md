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

1. **Read Level1 Global Index FIRST:** Read `harness_registry_path`. Find LAST STATUS=BOUND entry using the effective session id from `harness_current_session_id`. Use its WORKTREE_ROOT for the session.
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

#### 0.5 GH PREFLIGHT OBRIGATÓRIO (regra engineering-contracts §18 gh-cli-only + carregar comments do PR NO CONTEXTO)

Antes de QUALQUER outra operação no Modo A (PR URL), rode este bloco para: (a) garantir gh CLI disponível e logado, (b) CARREGAR NO CONTEXTO DA REVIEW **TODOS os comentários do PR (inline review comments + general PR body discussion comments + review-level comments)** pois eles influenciam fortemente nossa análise: se um colega já levantou um ponto, não queremos reportar a mesma coisa duplicada (ou se reportarmos, cross-linkar explicitamente e explicar se concordamos/discordamos).

```bash
# (a) Preflight gh
command -v gh >/dev/null 2>&1 || { echo "❌ gh CLI não instalado. Rode: install via https://cli.github.com/ + gh auth login --scopes repo,read:org,workflow"; exit 6; }
gh auth status >/dev/null 2>&1 || { echo "❌ gh CLI não autenticado. Rode: gh auth login --scopes repo,read:org,workflow"; exit 7; }

# (b) CARREGAR COMMENTS 3 fontes distintas (todas são importantes):
#     Source 1 = comments[]           → PR-LEVEL discussion comments (aba Conversation, genéricos, não atrelados a código)
#     Source 2 = reviewComments[]     → INLINE review comments (atrelados a hunks de código específicos, com reply threads)
#     Source 3 = reviews[]            → REVIEWS completas (APPROVED / CHANGES_REQUESTED / COMMENTED) + body do review + state
gh pr view <PR_URL> --json comments,reviewComments,reviews > /tmp/pr-<PR_ID>-all-comments.json
```

**Regra obrigatória sobre os comentários carregados (NÃO SKIP):**

1. **Ingestão e flatten:** Normalize os 3 arrays em uma única lista `PR_COMMENTS[]` onde cada item tem: `{source: "pr-comment" | "inline-review" | "review", id, path|null, line|null, author, state|null, createdAt, body, replyToId|null, resolvedStatus|null, isDraft, url}`. Ordenar por `createdAt` ASC para entender a linha do tempo de discussões.
2. **NÃO duplique findings.** Antes de classificar uma finding nova (Category 0/1/2/3/4/5), compare contra `PR_COMMENTS[]`:
   - **Match forte:** Se houver comentário inline (mesmo `path` + `line` ±10 linhas no mesmo diff hunk) com mesmo tema (ex: ambos falam de "missing null guard on `x.user`"), então:
     - Se o comentário do humano é mais completo e nós não temos mais nada a adicionar: **OMITA a finding, NÃO emita duplicado**; no lugar, adicione uma seção especial no relatório: **`🎯 Existing Human Review Threads (Not Repeated)`** listando (id, path, autor, 1-line resumo do ponto, status resolvido? resolvido por quem?).
     - Se temos informação adicional / discordamos / temos um exemplo reproduzível que o humano não colocou: **EMITA a finding normalmente mas comece com um prefixo OBRIGATÓRIO:**
       > `[Cross-ref PR inline comment #<id> by @<author> — extends / partially agrees / respectfully disagrees because <1 line rationale>]`
       e no final da finding adicione `→ Thread: <url>` apontando pro comentário original.
   - **Match fraco:** comentário em conversation-level geral ("this PR needs better error handling" genérico, sem path/line específico): não é duplicação, processe normalmente mas se nosso finding cobre exatamente aquele ponto → no final do relatório em `Existing Discussions Addressed In This Review` liste os pares.
3. **Review state aware.** Se `reviews[]` tem um `CHANGES_REQUESTED` recente de um OWNER/CODEOWNER, NÃO recomendamos `APPROVE` no final a menos que explicitamente o usuário peça override + temos 0C/0H + todos CR points foram abordados. Sempre inclua no resumo executivo uma linha: **`Current PR review state: <N> APPROVED, <M> CHANGES_REQUESTED (authors: @a, @b), <K> COMMENTED`**.
4. **Resolved threads não countam para findings a serem repetidas**, mas countam como histórico de discussão útil para entender trade-offs do autor → leia o body.
5. **Draft comments (`isDraft: true`)** são privados do autor e devem ser ignorados no processamento.

**Resultado esperado do Step 0.5:** Você tem em memória `ALL_COMMENTS[]` e `REVIEW_STATE_STATS`, e nas seções de output do relatório SEMPRE inclui as duas seções adicionais abaixo (entre `Executive Summary` e `Category 0`):
- `🎯 Existing Review Context (from PR comments)` — stats básicas + threads importantes ainda não resolvidas
- `🤝 Findings Alignment with Human Comments` — uma linha por finding ≥MEDIUM indicando se: (novo / duplicação omitida / estende humano / discorda humano)

#### 1.1 PR metadata + diffs

> Observação: o `comments,reviews,reviewComments` já foi buscado na etapa 0.5 acima (preflight gh + comments load). Abaixo buscamos apenas os demais fields (files, commits, etc) e o diff unificado.

```bash
gh pr view <PR_URL> --json \
  number,title,body,state,isDraft,baseRefName,headRefName,additions,deletions,changedFiles,commits,labels,reviewDecision,mergeable,files,author,assignees,maintainerCanModify
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
3. **Entity/enum definitions inside apps** (shared DB package pattern). Flag HIGH if apps define TypeORM entities / duplicate enums / own migration runners. All entities should live in the shared DB package detected by harness-xray (look for `@<scope>/db` / `packages/db` / project profile). Only bypass if project profile explicitly says "no monorepo DB package".
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

   **🔴 HARD RULE — INVERSÃO PROIBIDA (NUNCA faça isso):**
   > ❌ **ERRADO:** Reclamar que um teste NÃO tem `FLO-xxx` / `T<N>` / `AC<N>` no título.
   > ✅ **CORRETO:** Ter essas referências NO TÍTULO é ANTI-PADRÃO (ruim). Não tê-los e descrever APENAS comportamento observável é BOM / COMPLIANT.
   >
   > **Regra de decisão 1-sentence:** `Título contém FLO-ID? → BAD = FINDING. Título NÃO contém FLO-ID? → GOOD = NUNCA reporte finding por isso.`
   > **Traceabilty correta (NÃO viola REGRA 7.9):** comentário JSDoc `/** @ticket FLO-714 */` ACIMA do bloco, OU linha `// @ticket FLO-714 | @ac 3.2 | @task T1.4` COMO 1ª LINHA DENTRO do bloco. JAMAIS na string de título.

   Scan test files added/modified in the diff (`*.test.*`, `*.spec.*`, files inside `__tests__/`). Detect anti-patterns **EXCLUSIVAMENTE in the TITLE STRING** of `describe("...")` / `it("...")` / `test("...")`:
   - Ticket IDs: `FLO-\d+`, ticket-codes like `ABC-123` (qualquer prefixo 2+ letras + hífen + número no TÍTULO = BAD)
   - Task/item IDs: `Task? T\d+(\.\d+)?`, `Item \d+`
   - AC/section IDs: `AC\d+`, `§\d+(\.\d+)?`, `REGRA \d+`, `SPEC_XXX`, `PRD §`
   - Phase/story IDs: `Fase \d+`, `Story #?\d+`

   Severity (FINDING = BAD title = contém os patterns ACIMA):
   - 1–4 bad titles → **LOW WARN** (non-blocking, show in "Nice-to-have" list)
   - 5–9 bad titles → **MEDIUM** (appear in main findings; require rename before merge or explicit override comment)
   - ≥10 bad titles → **HIGH** (blocking: relatório de CI vai ser inútil, alguém quebra essa regra em escala)

   **❌ NUNCA gere finding por "ausência de FLO-xxx no título"** → Isso é o comportamento DESEJADO, compliant. Qualquer relatório que flagge ausência de task-id no título é uma REGRESSÃO na review skill, invalida essa seção do report.

   Never flag the JSDoc traceability comment ABOVE a block or a `// @ac X | @task Y | @ticket Z` line INSIDE the block as bad. Those are the RECOMMENDED way to keep traceability without polluting the display title.
6. **4.8 Route-level / failure-path test gap check (MEDIUM if missing)**. If Category 0 found a new webhook route event type → require 1 route-level signed-payload POST test (not just svc.handleEvent direct). If Category 0.3 flagged a tx pattern → require 1 failure path test: Stripe 5xx → tx rolls back + retry with same idempotency key → no double-effect. MEDIUM severity (waivable only with PR body sign-off override).

---

### Category 5: 🟡 Design Quality / Ousterhout RED FLAGS (engineering-contracts Appendix D D.1) — HIGH if RF01-RF04, MEDIUM if RF05-RF13

Appendix D canonical source → `skills/engineering-contracts/SKILL.md` "Appendix D — A Philosophy of Software Design (John Ousterhout)". This category never flags patterns explicitly requested in the ticket scope (downgrade to NIT waivable only if scope explicitly asked for the abstraction shape).

**How to apply this category (never guess — always diff-based):**

1. **RF01 — Shallow Module / Class / Abstraction (HIGH if NEW abstraction, 3+ files depend on it, API surface > implementation lines)**.
   - Trigger: Diff adds a NEW exported `class X`, `interface X`, `abstract class X`, `function createXService()` factory, or `useX()` hook, AND: (a) the abstraction has `> 8 public exports/methods` OR (b) 3+ OTHER files in the diff import from it, AND (c) total implementation LOC inside the abstraction is `≤ 1.2× the public API surface LOC` (lines of signatures/exports/types = ~same as implementation). This is Ousterhout #1 signature red flag: "new abstraction adds complexity without hiding any."
   - Downgrade to NIT if: scope file / task envelope explicitly says "create this interface / this generic hook for reuse across future features."

2. **RF02 — Information Leakage across module boundaries (HIGH if cross-package / cross-layer)**.
   - Trigger (scan imports + function args):
     - Service file in `packages/foo/src/services/x.ts` imports a DATABASE-SPECIFIC type (ex: `QueryRunner`, `EntityManager`, `SupabaseClient`) from a DB-only package and exposes it in any public function parameter or return type → caller must now know the DB engine = info leakage HIGH.
     - Backend route handler returns an internal DB entity CLASS directly (not a pick/omit/response DTO type) including internal fields (ex: `stripeIdRaw`, `authzCache`, internal enums) → frontend now knows backend schema details = HIGH.
     - Config parsing details (zod schema field names, `process.env.KEY` lookups) leak into component/service files (not just a typed config object) = MEDIUM.

3. **RF03 — Pass-Through Method / Handler Chain (HIGH if ≥3 layers deep with NO logic)**.
   - Trigger: Find a call chain `router.foo → service.foo(...args) → repository.foo(...args) → queryRunner.manager.getRepository(X).foo(...args)` where 2+ consecutive layers do NOTHING except pass the exact same args forward (no validation, no authz, no mapping, no idempotency key injection, no error wrapping, no metric emit). Flag HIGH per chain of depth ≥3 with ZERO added value per intermediate layer. If one layer adds authz or input validation only → flag MEDIUM (still suspicious but not pure passthrough).

4. **RF04 — Temporal Decomposition (HIGH if a business concept is split into classes/modules by PHASE instead of by DOMAIN ENTITY)**.
   - Trigger (file structure scan): If scope was "process a refund" → diff creates files like `RefundStep1Validate.ts`, `RefundStep2StripeCall.ts`, `RefundStep3UpdateDB.ts`, `RefundStep4EmitEvent.ts` with NO `RefundService.ts` / `Refund aggregate` file that OWNS the concept + invariant checks. Files grouped by WHEN they run (sequential phases) instead of WHAT domain concept they implement → HIGH. Correct shape = one module owns the concept and its invariants, exposes one method orchestrating the steps internally.

5. **RF05 — Repetition / Near-Duplicate Logic (MEDIUM if 2+ blocks, NIT if just formatting)**.
   - Scan for two+ blocks in the diff with `≥ 12 identical token sequences` in different files (not test fixtures). Flag MEDIUM unless scope explicitly says "ship fast with duplication now, DRY in follow-up PR" (documented in PR body).

6. **RF06 — Over-generic `<T>` with exactly 1 concrete caller (MEDIUM)**.
   - Trigger: Diff adds `class Foo<T>` or `function bar<T>()` or `interface X<T, U, V>` with 3+ generic params, AND there is EXACTLY 1 concrete instantiation/caller in the whole repo. If scope explicitly mentions "will be reused in epic Y" → downgrade to LOW waivable.

7. **RF07 — Comment / Over-comment Explaining WHAT, not WHY (MEDIUM if masking complexity)**.
   - Trigger: A `/* 5+ line comment block */` that literally restates the next 5 lines in English (ex: "Now we get the order and then we check if it's paid" followed by `const order = await repo.findById(); if (order.status === PAID) {...}`). If the code needs that much WHAT-comment → the abstraction is wrong; rename functions/extract helpers instead of prose. MEDIUM only if total comment-LOC ≥ implementation-LOC for that block.

8. **RF08-RF13 — Secondary flags (all MEDIUM, grouped):**
   - RF08: Boolean-flag hell = function with `≥ 4 boolean params` controlling internal behavior (prefer 2 separate functions / strategy 2-max).
   - RF09: Conjoined methods = one public function whose body does two conceptually unrelated things with a single shared error path (split).
   - RF10: Configuration/config flags explosion = `≥ 5 new YAML/env vars added` for ONE feature with no justification in scope (default-first, expose only what users must override).
   - RF11: Unused generality / unused extension point = NEW exported parameter, optional overload, or interface method that has ZERO callers in the diff and zero mention in the scope document.
   - RF12: Wrong naming = class/module name is a VERB (ex: `ProcessRefund.ts`) not a NOUN that owns responsibility (ex: `RefundProcessor` or better `RefundService`).
   - RF13: Hidden side effect in a getter/helper = function named `getX`, `loadX`, `findX`, `formatX` that actually WRITES / MUTATES / EMITS events internally.

**HARD RULE for ship integration §0.9.2 (≤2 HIGH findings auto-fix contract):** ANY Category 5 HIGH finding (RF01-RF04) counts TOWARD the same "≤ 2 HIGH total" ship-gate threshold alongside Categories 0–4 HIGHs. This means: 2 Category 5 HIGHs alone also triggers the Ask User / Request Changes path, just like Architecture HIGHs.

---

### Category 6: 🟡 Logging & Observability Anti-Patterns (engineering-contracts §12 + NEW §20) — HIGH for PII/raw-secret leaks, MEDIUM for verbosity/signal/levels

> **Canonical source for rules:** `engineering-contracts/SKILL.md` §12 (existing Observability & Logging) + §20 (new expanded Logging & Observability Standard, written 2026-09-01). Apply this category to any diff that: (a) adds new logger calls / console calls / echo statements, (b) adds new IO flow (HTTP / DB / file / CLI script / pipeline), (c) touches shell scripts / CI workflows / scripts, or (d) changes existing logger config (formatter / level / sinks). Flag severity follows the table below; never guess — always cite the EXACT anti-pattern ID.

**How to detect each anti-pattern:**

1. **L6.1 🔴 CRITICAL / HIGH — Raw PII / secrets in log output.** Diff contains literal `console.log(email)` / `logger.info({ phone })` / `echo "$user_input` or any logger.* call carrying raw `email`, `phone`, `address`, `stripe_id` (without hash), credit card digits, SSN, government ID, `sk_*`, `AWS_SECRET_ACCESS_KEY`, raw JWT token string, API keys in env dump full. Rule reference §20.6. Use hash / mask / omit.
2. **L6.2 🟠 HIGH — Wrong level: error as info or debug floods.** Examples: `logger.info(">>> ENTERING function foo` on EVERY internal call (noise); `console.error` used for expected handled branch that's NOT unrecoverable); logger.debug with full request payloads on prod default INFO level (leak volume).
3. **L6.3 🟡 MEDIUM — Missing structured correlation fields.** Diff writes logs as free-form string `"User did X"` sem contexto. Faltam: `traceId`, `spanId`, `correlationId`, `orgId`, `userId`, idempotency key (where applicable), structured fields discriminante `operation` ou `event`.
4. **L6.4 🟡 MEDIUM — Script / bash / CI workflow sem logging expressivo.** Shell script novo (>30 linhas) que NÃO tem echo em steps de IO ou usa um `set -x` flood SOZINHO sem mensagens semânticas. Ou tem echo sem níveis `[INFO]` / `[WARN]` / `[ERROR]` prefixados. Aplicar especialmente a scripts que escreve em bash, Makefile, GitHub Actions YAML `run:` blocos.
5. **L6.5 🟡 MEDIUM — Flood / log em loop / hot path verbose.** Dentro de um loop for N iterações, cada iteração dá um logger.info; ou hot path (<1ms por operação normal) tem 3+ logger calls; ou faz stringify JSON FULL de listas/arrays grandes sem truncamento. Regra 20.7 "No Flood Volume".
6. **L6.6 🟡 MEDIUM — Didn't follow repo existing logger wiring.** Repo tem um `@flockr/logger`, `@/server/logger.ts`, `OTEL provider`, `pino` configured singleton, `winston` transport, etc. — mas diff escreve `console.log` cru. Repo convention existente não foi seguida. Mesmo que o chamador não sabe, devemos detectar e usar o padrão (§20.4 "Use existing wiring first").
7. **L6.7 🔵 LOW — Empty catch block logging sem contexto.** `catch(e) { console.log("deu ruim") sem structured error; sem error message; sem stack trace estruturado; sem ID da requisição. BOM 1-liners. Melhor: logger.error({ err, op: "refund.create" }.

**Severity default:**
- L6.1 = HIGH ou secrets raw → CRITICAL se for ambiente prod persistente log; HIGH se só dev console; HIGH anyway;
- L6.2 / L6.5 = HIGH se a falha de nivel ruim;
- Demais itens → MEDIUM default;

**Coverage table row obrigatória (Coverage of Review /report deve incluir Category 6 checks:** Coverage of Review" com "✓ Yes — 8 categorias.

---

### Category 7: 🟢 Testing Gaps & Regression Lock (NEW QA-Centric ONDA1) — HIGH for missing tests on behavior change, MEDIUM for traceability comments, LOW for skip without ticket

> **Canonical enforcement companion rule:** harness-debugger-bugfix Step 1.2.5 REPRO AUTOMATION LOCK enforces the SAME rules for the bug-fix mode. This Category 7 applies for feature-mode diffs and code that touches runtime behavior / routes / UI components.

**How to detect each finding (diff-based, never guess — always cross-check the changed file list against `*test*`, `*spec*`, `__tests__/` additions):**

1. **G7.1 🟠 HIGH — ≥20 added lines of runtime behavior code WITHOUT any test file added/modified in the same diff.**
   - Compute: from `changedFiles[]`, count ONLY lines ADDED (`+` prefix in unified diff) in files under `src/` / `server/` / `app/` / `packages/*/src` / `components/` (exclude pure type-only `.d.ts`, pure interface files, enums-only files, index re-exports, config files, migrations-only `.ts`/`.sql`).
   - Also count ONLY files matching patterns `*.test.*`, `*.spec.*` inside `__tests__/`, `test/`, `spec/` directories in changedFiles.
   - If behavior additions ≥20 lines AND test file count added/modified = 0 → **HIGH G7.1 = MISSING TESTS FOR NEW BEHAVIOR.**
   - **EXEMPTIONS (waive G7.1 only if body match):**
     - Conventional commit TYPE is `refactor:` AND commit body includes the phrase `"renames only"` or `"no behavior change"` — AND you can visually confirm the diff is only variable/class/file renames.
     - Conventional commit TYPE is `style:` (Biome formatting, whitespace, CSS-only cosmetic with no semantic change).
     - Conventional commit TYPE is `docs:` / `chore(ci):` / `chore(deps):` bump-only — AND zero runtime src/ files changed.
     - Conventional commit body contains an EXPLICIT override declaration `QA_OVERRIDE: "no test possible here: <1-line justification>"` signed-off by a codeowner in the PR body.
   - **Fix suggestion (when flagged):** Add a behavioral spec (unit preferred, integration if ≥2 modules cross; route-level for REST/tRPC; Playwright for UI) matching the behavior. At minimum, write 1 happy-path + 1 sad-path per new exported function / route mutation.

2. **G7.2 🟠 HIGH — Public API change OR interactive UI component added without integration/Playwright test.**
   - **Branch A (Public API):** Diff touches ANY file that is a tRPC router (ex: `server/api/routers/xRouter.ts` mutates) or REST handler (`route.ts`, `app/api/*/route.ts`, `server/webhooks/*`) OR exposes a new exported function from a package's public `exports` field in `package.json`. AND same diff does NOT contain an addition/modification of a route-level test file (ex: `*.api.test.ts`, `__tests__/e2e/*`, `test/integration/router-*.spec.ts`). → **HIGH G7.2a.**
   - **Branch B (Interactive UI component NEW):** Diff adds a NEW `.tsx` file that exports a user-visible interactive component (Button/Dialog/Form/Modal/Combobox/DatePicker/Tabs/Table/AutoComplete — keywords in filename or JSX elements containing handlers `onClick`, `onSubmit`, `onChange`, `useState`, `useReducer`, `useForm`, `useMutation`). AND no corresponding RTL/Playwright spec file for that component exists in the diff. → **HIGH G7.2b.**
   - **Exemptions (waive only with explicit confirmation):** Component is explicitly marked DEMO/SCAFFOLD in filename (ex: `*Demo*.tsx`, `*Scaffold*.tsx`) + PR body has the warning. OR route is strictly internal / health-check (`/healthz` route).
   - **Fix:** Add 1 route-level test (for API branch A) calling `trpcClient.xxx(...)` or `POST /api/xxx` with signed payload + valid auth; for UI add 1 RTL spec calling `fireEvent.click` + assertions.

3. **G7.3 🟡 MEDIUM — New/modified test WITHOUT traceability comment linking to SbE behavior or ticket.**
   - Scope: scan EVERY test file (`*.test.*`, `*.spec.*`) NEW or MODIFIED in the diff. For each `it(...)` / `test(...)` block body, check the FIRST 3 non-empty lines inside the curly braces (or the JSDoc comment `/** ... */` IMMEDIATELY above the nearest enclosing `describe()`).
   - Look for a comment line MATCHING the regex: `^\s*//\s*@(ac|ticket|task|bug)\s+(B-\d+|FLO-\d+|AC\d+(\.\d+)?|T\d+(\.\d+)?|AB-\d+)` or equivalent JSDoc tag `@ticket`, `@ac`, `@task`.
   - If the test block has ZERO such comment inside (or JSDoc above nearest describe missing it) → **MEDIUM G7.3 = NO TRACEABILITY from behavior table to test body.**
   - **Exception (waive G7.3):** It's a pure test infrastructure refactor (rename, package.json updates, moving files across folders, jest/vitest config only). OR it's a well-known canonical test (ex: `it("sums 2+2")` = unrelated to SbE scope).
   - **Fix:** Add 1 line as FIRST executable line inside the `it()/test()` block: `// @ac B-3 | @ticket FLO-123` (or JSDoc block for describe). This is the canonical SbE traceability anchor used by scope-checker CHECK2 bilateral verification.

4. **G7.4 🔵 LOW — `.skip()` / `xit()` / `it.todo()` used WITHOUT a follow-up ticket reference.**
   - Scan test blocks for `.skip(` or `xit(` or `it.todo(` or `test.skip(` or `test.todo(`.
   - Check 10 lines around the declaration for a comment MATCHING regex: `TODO\((FLO-\d+|PROJ-\d+|#\d+|issue #[^\s)]+)\)` or `Blocked on PR #\d+` or `Requires: <dependency>`.
   - If `.skip` exists AND no follow-up ticket reference → **LOW G7.4 = SKIPPED TEST WITH NO FOLLOWUP.**
   - **Exception:** `it.skip` inside a Scratch `.test.ts` file clearly named `scratch.*` or `_WIP_*` (developers use these locally — only flag if the file is staged to be committed).
   - **Fix:** Add 1 line comment above the skip: `// TODO(FLO-123): reason = blocked on PR #456`. OR remove the skip entirely and make the test pass.

**Severity defaults enforced on the ship-gate threshold (§0.9.2 auto-fix rule ≤2 HIGH count):**
- G7.1 + G7.2 = HIGH severity (BLOCKING if total HIGH ≥3 in the same review alongside other Category 0-8 HIGHs; if ≤2, auto-fix rule triggers on code-review ship gate).
- G7.3 = MEDIUM.
- G7.4 = LOW.

**Coverage of Review /report MUST include Category 7 in the table (see Coverage section §N-1 below).**

---

### Category 8: 🟣 UI Selector Contract Hygiene & data-testid 3-part Convention (NEW QA-Centric ONDA1) — HIGH for fragile selectors or NEW interactive components w/o ids, MEDIUM for naming convention, LOW for duplicate ids on list rows

> **Canonical source for the UI selector contract rule:** harness-spec SbE §4.2 Behavior Example Tables — new column "UI Selector Contract" binds Playwright/RTL tests to stable ids. Testing Library Priority Order (canonical Kent C. Dodds, 2023): **ByRole > ByLabelText > ByPlaceholderText > ByText > ByDisplayValue > ByAltText > ByTitle > ByTestId (last escape hatch for dynamic content)**. When ByRole (with accessible name) is STABLE and UNIQUE for the element across renders → data-testid is NOT required. The purpose of data-testid is to cover UI that has unstable/translated/no accessible text: toast messages, icon-only buttons, spinners, loading states, table row action buttons.

**Convention MANDATORY for ANY `data-testid` the diff introduces / modifies (3-part kebab-case with double-underscore separator):**
```
<domain>__<component-or-screen>__<action-or-element>
```
Examples (correct):
- `creator-bookings__refund-dialog__confirm-button`
- `public-events__event-card__buy-now-button`
- `scanner__scan-screen__qr-input`
- `auth__login-form__submit-btn`
- (for repeated list rows: append `--<unique-id>` suffix) `creator-bookings__row__refund-button--order-abc123`

Anti-patterns (flag G8.3 if used):
- ❌ `refundButton` (no separator; camelCase not kebab)
- ❌ `creator_bookings_refund` (single underscore instead of double `__`)
- ❌ `bookings--refund--button` (triple hyphen not part separator)
- ❌ `cancel` (too generic, 0 parts, no domain context — becomes ambiguous when you have 12 cancel buttons in app)

**How to detect each finding (8.1 → 8.4):**

1. **G8.1 🟠 HIGH — NEW interactive/visible user-facing component (or NEW screen) created WITHOUT data-testid on elements that NEED it (per priority-order rule).**
   - Compute: from changedFiles, list `.tsx` / `.jsx` / `.vue` files with status `A` (added) OR `.tsx/.jsx` that export new components (filename includes `Button`, `Dialog`, `Modal`, `Form`, `Tabs`, `Select`, `Combobox`, `DatePicker`, `AutoComplete`, `Dropdown`, `Drawer`, `Snackbar`, `Toast`, `Card`, `Input`, `Table`, `Alert`).
   - For EACH NEW interactive element in JSX:
     - Is `ByRole + accessible name (label/text)` provably stable AND unique? → EXEMPT (Button with static text `<button>Confirm Refund</button>` → no id needed, `getByRole('button', {name: 'Confirm Refund'})` is stable).
     - Is element icon-only button? `<Button><TrashIcon/></Button>`? Loading spinner? Toast message? Progress bar? Empty-state illustration? Table row action icon (duplicate across N rows)? → DATA-TESTID REQUIRED.
     - Does text change based on translations (i18n) / feature flags / dynamic org/user state? → `ByText` fragile → DATA-TESTID REQUIRED.
   - If ≥1 such element in the NEW component lacks a `data-testid=""` attribute → **HIGH G8.1 = NO SELECTOR CONTRACT FOR FRAGILE ELEMENTS.**
   - **Exemption:** Component is explicitly a PURE presentational `<div>` wrapper with ZERO handlers, ZERO user interaction (cannot click/type/hover/focus it). Or PR body has explicit QA_OVERRIDE: `G8.1 WAIVED: all content has stable ByRole + accessible names`.
   - **Fix:** Add `data-testid="<domain>__<component>__<element>"` for every element that fails stability check. For icon buttons, prefer aria-label FIRST (so screen readers work too), THEN add data-testid as a secondary selector contract.

2. **G8.2 🟠 HIGH — NEW/MODIFIED TEST FILE uses a PRIMARY selector that is FRAGILE: CSS class, XPath, nth-child(N), regex text, or getAllByRole indexed.**
   - Scope: scan EVERY test file (`*.spec.ts`, `*.test.tsx`, inside `playwright/`, `e2e/`, `__tests__/`) that is NEW or MODIFIED in the diff.
   - Flag HIGH if the PRIMARY selector (first element-fetch call in the 1st/2nd line of a test block, or the selector used for an action like `click()`/`fill()`) uses ANY of these anti-patterns:
     - CSS class selector: `.css-class-name` → ❌ `page.locator('.btn-primary')` or `container.querySelector('.save-btn')`
     - XPath: `//div[2]/button[3]` or any `//` prefix → ❌ (structure changes = test breaks)
     - `nth-child(N)` pseudo / `.getAllByRole('button')[3]` / `.first()` / `.nth(N)` when N≥1 on a list — ❌ (order changes = breaks)
     - `getByText(/partial.*regex/)` with vague regex that can match another 2+ DOM elements (false-positive risk).
   - **ALLOWED EXEMPTIONS for G8.2 (waive if verified):**
     - Playwright `getByRole('button', { name: 'Save changes' })` — stable accessible role + name → ALWAYS ALLOWED (preferred over data-testid).
     - RTL Testing Library `screen.getByLabelText('Email address')` on labeled inputs → stable → ALLOWED.
     - `getByTestId('creator-bookings__refund-dialog__confirm-button')` using the valid 3-part convention → ALLOWED.
   - **Fix:** Rewrite the primary selector to `getByRole(...)` (preferred, if stable unique accessible name exists) ELSE `getByTestId('<valid 3-part id>')`. For list rows, use `--<unique-id>` suffix + `getByTestId('x-row__action--' + rowId)`.

3. **G8.3 🟡 MEDIUM — data-testid attribute exists but DOES NOT follow the 3-part convention.**
   - In NEW files: any `data-testid="..."` string that FAILS the regex match:
     ```
     ^[a-z0-9][a-z0-9-]*__[a-z0-9][a-z0-9-]*__[a-z0-9][a-z0-9-]*(--[a-z0-9][a-z0-9-]*)?$
     ```
   - For MODIFIED files: only flag `data-testid` values that were WRITTEN/CHANGED in this diff (don't flag existing dirty ids from legacy commits — blast radius only).
   - If a non-conforming id exists AND file is not LEGACY (modified from pre-existing commit) → **MEDIUM G8.3 = NON STANDARD TEST ID FORMAT.**
   - **Exception:** Explicit override `G8.3 CONVERTED LATER: <ticket>` in PR body with a ticket reference for a follow-up refactor batch (low-risk incremental cleanup).
   - **Fix:** Rename the data-testid to canonical `domain__component__element[--unique-row]` form. Search for all references in spec files and rename there too.

4. **G8.4 🔵 LOW — Duplicate identical data-testid in list/tabular renders without per-row unique suffix.**
   - Pattern: Inside a `.map()` / loop over an array (JSX lists, tables, grid rows, tab panels), the SAME data-testid string is emitted for EACH row of the iteration with no suffix that distinguishes row `<unique-id>`.
   - Example flagged: `<Button data-testid="orders__table__cancel-button">` inside `orders.map(order => ...)` (rendered N times, 10 rows = 10 identical ids → Playwright/RTL `getByTestId` throws `Found multiple elements` error and forces fragile `.first()`).
   - Example correct (waive): `<Button data-testid={'orders__table__cancel-button--' + order.id}>`
   - If duplicate pattern exists → **LOW G8.4 = AMBIGUOUS DUPLICATE TESTID IN LIST.**
   - **Fix:** Append `--` + the unique entity primary key (order.id, booking.uuid, event.slug) to the 3-part canonical id.

**Ship threshold enforcement for G8 findings:**
- G8.1 + G8.2 = HIGH (both count toward the §0.9.2 ≤ 2 HIGH total ship rule).
- G8.3 = MEDIUM.
- G8.4 = LOW.

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
- Category: Pipeline Integrity / Runtime / Security / Architecture / Scope / Design Quality (Ousterhout)
- File:line
- Snippet (3 lines before + 3 lines after, from patch)
- Why this is a problem (evidence-based — never "I don't like it")
- **Explicit rule citation (MANDATORY when possible)**: quote the EXACT project rule file:line from .claude/rules/*.md / AGENTS.md / decision docs you read during bootstrap. Example: "viola [architecture.md](file:///.../.claude/rules/architecture.md#L12) 'Router → Service → Repository: Routers must not contain business logic >30 lines'". For Category 5: ALWAYS cite `engineering-contracts/SKILL.md` Appendix D D.1 with the RF number (ex: "viola Appendix D RF03 — Pass-Through Method ≥3 layers").
- Actionable fix — specific lines/what should replace
- Optional: suggest code change snippet ONLY if obvious. NEVER rewrite whole file.

**N-1. Coverage of Review TABLE** (OBRIGATÓRIO — usuário confia audit):
- 7 rows obrigatórias: §1.5 Bootstrap → Category 0 Pipeline Integrity → Category 1 Runtime → Category 2 Security+PII+Authz audit → Category 3 Architecture/Repo boundary → Category 4 Scope deviation / Demo UI / Test naming → Category 5 Design Quality / Ousterhout RF01-RF13
- Non-goals (style/format/coverage%) → Skipped intentionally note.

**N. Final verdict section (template):**

Then at the end (both modes, except verdict notes):
- **Verdict**: 🔴 Request changes (≥1 CRITICAL or ≥2 HIGH) / 🟡 Approve with comments (only MEDIUMs/LOWs) / 🟢 Approve
  - **Mode B NOTE**: Verdict labels above refer to "if this were submitted as a PR". Since it's local work-in-progress, interpret as: 🔴 = Fix these before committing/pushing; 🟡 = Fix before merging; 🟢 = Clean.
- **Blocker summary**: numbered list — each CRITICAL/HIGH must be fixed before merge (or before commit+push in Mode B)
- **Non-blocker nice-to-have**: numbered list — MEDIUM/LOW, fix or ignore, user decides

---

## 4.9 🔴 STORAGE PREFLIGHT OBRIGATÓRIO (NUNCA SKIP — engineering-contracts §20 + HARNESS_RULES.md STORAGE BOUNDARY)

> **HARD STOP RULE VERBATIM DO USUÁRIO:** Nenhum asset do trabalho do harness deve ser criado na worktree. Apenas quando solicitado explicitamente. Tudo deve ser organizado no harness-sessions.

**Antes do PRIMEIRO write em disco (qualquer arquivo: report, screenshots, decisions, QA evidence, etc), RODAR EXATAMENTE ESTE BLOCO:**

```bash
# (1) Source o contrato canônico de sessões (fornece harness_output_path, harness_assert_outside_worktree, etc)
HARNESS_HOME="${HARNESS_HOME:-$HOME/.trae}"
CONTRACT="$HARNESS_HOME/contracts/harness_sessions_contract.sh"
if [ -f "$CONTRACT" ]; then
  # shellcheck disable=SC1090
  source "$CONTRACT"
else
  echo "❌ FATAL: harness_sessions_contract.sh não encontrado em $CONTRACT. Não posso escrever outputs sem o storage boundary. Abortando write."
  exit 98
fi

# (2) Definir variáveis mínimas para binding (se já houver binding, reuse; senão usar defaults seguros)
# WORKTREE_ROOT: obrigatório se Mode B; se Mode A sem worktree local, set para string vazia mas NÃO CAI NA WORKTREE POR ACIDENTE
# SESSION_ID: harness_current_session_id do registry ou fallback slug-safe
SESSION_ID="${HARNESS_CURRENT_SESSION_ID:-fallback-review-session}"
# WORKTREE_ROOT: se Mode B, já temos; se Mode A e user passou --worktree, use aquele valor; senão vazia (sem assert contra worktree nesse caso)
# WORKTREE_ROOT é conhecido no fluxo desde §0.1 e §Mode B; aqui apenas reafirmar

# (3) Computar paths canônicos + criar diretórios base (SESSION_DIR, WORKSPACE_SHARED, etc)
# Se WORKTREE_ROOT existe e é válido:
if [ -n "${WORKTREE_ROOT:-}" ] && [ -d "$WORKTREE_ROOT" ]; then
  harness_compute_paths "$WORKTREE_ROOT" "$SESSION_ID" "$PWD"
  harness_ensure_session_dirs "$WORKTREE_ROOT"
  # Double-guard: o helper harness_output_path já roda assert automaticamente; mas reafirmar aqui para clareza
  harness_assert_outside_worktree "$HARNESS_SESSION_DIR" "$WORKTREE_ROOT" "HARNESS_SESSION_DIR (root de efêmeros)"
  harness_assert_outside_worktree "$HARNESS_WORKSPACE_SHARED" "$WORKTREE_ROOT" "HARNESS_WORKSPACE_SHARED (root duráveis)"
fi

# ⚠️ APÓS este bloco, NÃO construa paths manualmente.
# Use SEMPRE: OUTPUT_PATH="$(harness_output_path "<type>" "<slug>" "<related_id>" "<scope=session|workspace>" "<ext>" "<suffix>")"
# Garantias automáticas do helper: timestamp prefix UTC ordenável, subpasta por type/related_id, mkdir -p, assert outside worktree, fallback seguro.
```

---

## 5. Post-report actions

> **IMPORTANTE: STORAGE BOUNDARY — NUNCA escreva dentro da worktree. Todo output via `harness_output_path` only (ver §4.9).**

### Mode A (GitHub PR):
- **Construir o path do report USANDO O HELPER (nunca manual):**
  ```bash
  # Report principal (full) — related_id = pr-<ID>; ficará agrupado em reviews/pr-<ID>/
  REPORT_FULL_PATH="$(harness_output_path "review" "harness-code-review" "pr-${PR_ID}" "session" "md" "full")"

  # Se houver um segundo report da MESMA PR (ex: postfix, post-review, auto-fix summary) — usar outro suffix:
  # REPORT_POSTFIX_PATH="$(harness_output_path "review" "harness-code-review" "pr-${PR_ID}" "session" "md" "postfix")"
  ```
  - **Resultado esperado no filesystem:**
    ```
    $HARNESS_SESSION_DIR/reviews/pr-<ID>/
      ├── 20260902-092400-harness-code-review_full.md   (1ª rodada, prefix timestamp ordena primeiro)
      └── 20260902-093000-harness-code-review_postfix.md (2ª rodada, prefix timestamp ordena depois)
    ```
    Busca futura trivial: `ls -1 reviews/pr-382/*.md` → todos reports da PR juntos, ordem alfabética = ordem cronológica.
  - **Fallback seguro SEM binding (raro):** o helper `harness_output_path` já cai em `$HARNESS_HOME/outputs/fallback-session/reviews/pr-<ID>/...` automaticamente; NUNCA cai na worktree nem em `./reports/`.
  - **NUNCA use path relativo `./reports/` ou `$WORKTREE_ROOT/.trae/`. MORATÓRIA engineering-contracts §20.**

- **DO NOT approve or request changes DIRECTLY on GitHub via `gh pr review`** unless user explicitly asks after seeing the report and saying "suba isso como review oficial". Our first deliverable = the report for the user to review in chat.
- If there are ZERO findings → still write a report saying "No CRITICAL/HIGH issues found; scope matches; dependencies justified." + list what you checked so user trusts the review was actually done.
- **Escrever usando atomic write:** pipe o conteúdo markdown no stdin de `harness_write_file_atomic "$REPORT_FULL_PATH"` (tmp → mv atômico, evita meio-escrito em crash).

### Mode B (Local Worktree):
- **Construir o path do report USANDO O HELPER:**
  ```bash
  # Worktree slug: extrair basename de WORKTREE_ROOT (ex: feat-FLO-714--Design-a-non-blocking-and-scalable-deployment-in-prod-governance)
  WT_SLUG="$(basename "${WORKTREE_ROOT%/}")"
  REPORT_LOCAL_PATH="$(harness_output_path "review" "harness-code-review" "worktree-${WT_SLUG}" "session" "md" "full")"
  # Segunda passagem da mesma worktree: trocar suffix para "pass2" ou "postfix" etc
  ```
  - **Resultado esperado:** `$HARNESS_SESSION_DIR/reviews/worktree-<WT_SLUG>/20260902-101500-harness-code-review_full.md`
  - Timestamp UTC no prefix garante ORDENAÇÃO de múltiplas passes locais sem depender de mtime do SO.
- **DO NOT interact with GitHub at all** in Mode B (no gh commands, no PR creation). Pure local output only inside harness-sessions.
- Zero findings → still write report with: "No CRITICAL/HIGH issues found in modified files. Scope matches stated goals; dependencies justified." Include the full changed files list + what you checked per category.
- Optional user convenience at end of chat message:
  - If Mode B, after presenting findings, offer ONE follow-up action:
    - `[Apply fixes locally]` — if user says yes, proceed using harness-developer mindset to fix the CRITICAL/HIGH blockers inside the same worktree (still under scope; don't add features). **Nota: QA evidence / screenshots dessa etapa também via harness_output_path type=qa scope=session.**
    - `[Show just the blocked items condensed]` — for brevity.
    - `[Nothing, thanks]` — stop.
  Don't be pushy. If user just says "ok thanks" → stop.
