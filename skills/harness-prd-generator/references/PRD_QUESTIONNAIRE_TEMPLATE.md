# PRD QUESTIONNAIRE — Structured 4-Batch

> Used by harness-prd-generator to gather input in a safe, non-overwhelming cadence.
> Each batch has 4-8 questions max. Ask one batch. Wait for answers. Follow up 1-2 clarifying per answer
> if it misses obvious edge cases, then move to next batch.

---

## Pre-Questionnaire: CRITICAL REPO ANALYSIS (must complete first)

First, fill this table using evidence from the worktree (grep, glob, existing patterns):

| Dimension | Overall risk (L/M/H) | HIGH findings count | Key files / areas to watch |
|---|---|---|---|
| Performance | — | — | — |
| Security + PII (RLS/PII-hash) | — | — | — |
| Scalability (DB volume/idempotency) | — | — | — |
| Maintainability (cross-package blast) | — | — | — |

Present this to the user BEFORE any questions. User acknowledges or adds comments.

---

## Batch 1 (Strategy + Problem) — 4 questions

### Q1: Overview (1-paragraph: "what" + "why it matters")
**Prompt**: "Em 1 parágrafo: qual é essa feature e por que ela importa para o Flockr hoje? Responda no estilo: 'X é uma nova funcionalidade que faz Y, permitindo que organizadores/atendentes Z. Isso importa porque hoje acontece W e causa [perda de receita / churn / atraso operacional / risco regulatório].'"
**Repo-grounded hint to include in actual question**: "[Se repo é Lumos: exemplo: Flockr é plataforma UK-first; hoje no dashboard do organizador não tem botão p/ Stripe Dashboard; causa SLA X...]"

### Q2: Problem Statement + concrete example
**Prompt**: "Descreva, em 1 parágrafo + 1 bullet com caso concreto: o que está quebrado ou faltando hoje? Inclua persona (organizador / atendente / admin) + momento (checkout / pós-venda / dashboard) + impacto (£ perdido / atraso em X minutos / risco SLA)."
**Follow-up if answer is vague**: "Você consegue dar um exemplo passo-a-passo: como um usuário chega nesse problema hoje, passo 1, 2, 3, 4 — e onde ele trava?"

### Q3: Goals (3-6 S.M.A.R.T. goals)
**Prompt**: "Liste 3 a 6 objetivos SMART (Specific Measurable Achievable Relevant Time-boxed). Formato cada linha:
  - 'Objetivo 1: [o que] até quando; medida de sucesso: [métrica % / £ / N]'
  Exemplo: 'Até fim de Q3, 80% dos organizadores conectados ao Stripe usam o botão 1-click → pular 3 telas de navegação (reduz tempo até dashboard de 37s para 4s)'"
**Repo-grounded hint**: "[Se Stripe Connect / tickets: hoje temos N contas conectadas; meta realista = 80% usage em 4 semanas p/ release...]"

### Q4: Non-Goals (2-5 bullets, EXPLICIT out of scope)
**Prompt**: "O que explicitamente NÃO faremos nesta iteração? (Essa seção é a mais importante do PRD — ela previne scope creep nos 3 próximos meses.) Liste 2-5 bullets:
  - 'Não implementaremos [X] (fica para release 2)'
  - 'Não daremos suporte a [caso de uso raro / internacional] nesta release'
  - 'Não mudaremos [sistema existente Y] — isso fica para PRD separado'"
**Repo-grounded follow-up example**: "Se feature for Stripe: 'Não vamos implementar payout scheduling, só redirect p/ dashboard Stripe — ok?' (previne FRs espúrios)."

---

## Batch 2 (Users + Stories + FRs) — 4 questions

### Q5: User Stories table (3-7 rows)
**Prompt**: "Preencha essa tabela. É obrigatório ter no mínimo: (1) 1 linha persona feliz happy-path organizador, (2) 1 linha persona feliz attendee/público (se aplicável), (3) 1 linha de permissão negada (usuário sem role tenta acessar funcionalidade):

| As a [role] | I want to [action + object] | So that [business value] |
|---|---|---|
|  |  |  |
"
**Follow-up if table < 3 rows**: "Adicione pelo menos a linha de permissão negada — todo FR vai ter que validar AC de auth, e se a história não existir, a gente esquece desse AC."

### Q6: Functional Requirements (FR-1..FR-N; each with 3 edge cases MINIMUM)
**Prompt**: "Liste N requisitos funcionais, nomeados: FR-1 Nome, FR-2 Nome, ... (pelo menos 5). Para CADA FR, responda:
  - Descrição (o que acontece, passo a passo)
  - Trigger (quando dispara: user click, webhook, cron)
  - Input (dados que entram: required + optional fields, com tipos)
  - Output (sucesso: dado retornado, tela redirecionada, etc)
  - 3 edge cases MÍNIMOS:
    - (a) Erro de permissão (usuário não autorizado)
    - (b) Input malformado / vazio
    - (c) Race / double click / retry (idempotência)
    Extras (se aplicável): timeout serviço externo, limite excedido, serviço down"

### Q7: Idempotency + Retry behaviour (mini FR)
**Prompt**: "Para funcionalidades que envolvem clique em botão (redirect, pagamento, criação de recurso):
  - Usamos idempotency key? (Sim/não + detalhe)
  - Double click proteção no frontend? (Sim = debounce 500ms + disabled durante loading)
  - Em caso de erro de rede: usuário clica de novo. Ação é criada duplicada? (Resposta desejada: 'não, porque usamos unique constraint + idempotency key' — se a resposta for 'sim' → problema a resolver no AC.)"

### Q8: FR Confirmation — any hidden behaviors?
**Prompt**: "Existe algum comportamento implícito? (Ex.: se feature for 'botão redirect': abre em new tab? É valido para organizadores com conta Stripe não conectada? O que acontece se a conta conectada estiver com status restricted no Stripe? — liste todos comportamentos ocultos que não entraram em FRs.)"

---

## Batch 3 (NFRs + Data Model + System Interactions) — 5 questions

### Q9: Non-Functional Requirements table
**Prompt**: "Preencha a tabela (pelo menos 7 linhas obrigatórias):

| Requirement | Target |
|---|---|
| Latency (p95) |  |
| Availability |  |
| Data retention (UK GDPR default 12mo unless accounting 6y) |  |
| Accessibility (WCAG 2.x AA default) |  |
| PII redaction + hashing level (which fields are NEVER logged raw?) |  |
| Observability (what structured events are logged; trace-ids required?) |  |
| Security (RLS enable/disable on new tables; auth role check at endpoint) |  |
"
**Follow-up**: Moeda: "Moeda padrão GBP em minor units (pence, integer). Confirmar: NÃO usamos float para £ nunca."

### Q10: Data Model — New / changed tables
**Prompt**: "Se a feature tocar banco:
  - Quais tabelas NOVAS? (1 tabela por bloco:)
    ```
    table_name
      column  type       nullable   notes (inclui RLS: who can read / who can write)
      ...
    ```
  - Quais tabelas EXISTENTES são alteradas (novas colunas / índices)?
"
**Repo-grounded hint**: "[Se Supabase Postgres Flockr: RLS é obrigatório em NOVA tabela. Incluir linha: `ENABLE ROW LEVEL SECURITY;` + policies para organizer / admin / anon.]"

### Q11: Migrations required
**Prompt**: "Nomeie cada migration com nome padrão TypeORM/Supabase:
  - `migration:create AddXxxColumnToYyyy` → descrição 1 linha
  - `migration:create CreateXxxTable` → descrição 1 linha
  - `migration:create CreateIndexForZzzz` (se FK / consulta frequente)
Para cada migration: rollback possível? (sim/depende? Se dependência forte de dados → resposta.)"

### Q12: System Interactions + 3rd-party calls
**Prompt**: "Liste TODOS serviços internos / externos que feature chama. Exemplo:
  - Stripe API: `GET /v1/accounts/{id}/login_links` (nome + método + endpoint se souber)
  - tRPC router interno: `stripeConnect.getDashboardUrl` (nome)
Para CADA um:
  - Timeout default? 3s / 10s?
  - Retry: 0 / 1 / 2 retries com exponential backoff? Quais códigos HTTP são retryable?
  - Failure mode: degrade gracefully (mensagem user-friendly) ou hard-fail (HTTP 500)?
  - Se webhook: qual endpoint recebe? idempotency de delivery?"

### Q13: Mermaid diagram required
**Prompt**: "Descrever em alto nível o fluxo. Depois o gerador produz:
```mermaid
sequenceDiagram / flowchart
    A->>B: Request
    B->>C: Check RLS
    etc.
```
Confirmar: componentes A, B, C, D = nomes corretos do repo (ex: User, Server Component, tRPC stripeConnect router, Stripe API, DB)."

---

## Batch 4 (Dedup / Normalisation / AC / Open Qs) — 4 questions

### Q14: Deduplication / Update Rules
**Prompt**: "Se há upsert ou create-or-update de qualquer registro:
  - Chave primária / matching (da mais forte para mais fraca): Ex: (1) idempotency_key, (2) user_id + event_id UNIQUE, (3) email + nome approx
  - Comportamento ao dar match: overwrite TUDO? / fill nulls only? / no-op?
  - Comportamento de deleção: soft-delete deleted_at timestamp? hard-delete? archive? (UK GDPR: direito ao esquecimento → hard delete obrigatório em 30d se usuário pedir, exceto dados contábeis reter 6 anos.)"

### Q15: Normalisation rules
**Prompt**: "Para CADA tipo de dado listado abaixo, qual a regra de normalização padrão:
  - Moeda: GBP pence (integer, minor unit, 100 = £1.00). Confirmação sim/não.
  - Datas: armazena UTC, exibe Europe/London (Fuso UK). Confirmação sim/não.
  - Email: lowercase + trim + validar RFC 5322 padrão repo? Sim/não.
  - Telefone (se aplicável): formato E.164 (+44...) Sim/não.
  - UK postcode (se aplicável): normalize (UPPER, trim internal space to exactly 1) Sim/não.
  - Nome (próprio / evento): trim + título? Apenas trim? Qual?"

### Q16: Acceptance Criteria (8-20 numbered checkboxes, MÍNIMO 8)
**Prompt**: "AC é testável — cada checkbox deve ser um passo verificável. Lista obrigatória mínima (adicione os específicos da feature):
  - [ ] AC-1 Happy path organizador logado + role ok: executa ação com sucesso + resultado correto.
  - [ ] AC-2 Role permission denied: atendente / usuário sem acesso → recebe 403 (ou redirecionamento seguro, 302), SEM dados vazados.
  - [ ] AC-3 Input malformado (ex: campo required nulo / string vazia): retorna 400 com mensagem de erro clara.
  - [ ] AC-4 Duplo clique / idempotência: mesmo botão clicado 2x em 200ms → só 1 ação é executada (nenhum recurso duplicado, nenhum £ duplicado).
  - [ ] AC-5 RLS: usuário organizador A não pode ler/destruir recurso de organizador B (se envolver DB + nova tabela) — retorna 404.
  - [ ] AC-6 Serviço externo falha (timeout / 5xx): usuário vê mensagem de erro amigável, NÃO stacktrace exposto; não tem estado parcial gravado a menos que transaction.
  - [ ] AC-7 Accessibilidade (UI): teclado navega com TAB order lógico; contraste WCAG AA 4.5:1.
  - [ ] AC-8 (webhook, se aplicável): mesmo evento enviado 2x (Stripe retry) → idempotência OK, sem duplicatas.
  + ... (adicione ACs específicos da feature, 8-20 no total)"

### Q17: Open Questions (P0 blocks implementation)
**Prompt**: "Liste 5-10 perguntas abertas, classificando por P0/P1/P2.
  P0 = bloqueia implementação; deve ser respondida ANTES do PRD ser Approved.
  P1 = importante; pode ser resolvido durante desenvolvimento mas não bloqueia início.
  P2 = nice-to-have; decisão posterior.

| # | Question | Priority | Resolution |
|---|---|---|---|
| 1 |  | P0/P1/P2 | blank |
"
**Examples for Flockr/Stripe**:
  - "P0: Contas Stripe Connect com status 'restricted' → mostramos o botão? Sim (Stripe bloqueia internamente) / Não (ocultamos, mostramos toast 'complete sua onboarding')?"
  - "P1: Quais métricas coletamos no analytics? (click-through, conversão para dashboard open, % por role)"
  - "P2: Internacionalização para galês (cy-GB) no texto do botão nesta release?"

---

## Post-Questionnaire: Critical Gap Auto-Check (must run BEFORE writing PRD)

Before outputting PRD, iterate over these and flag P0 if missing:

| Check # | Validation rule | Pass/Fail | P0 gap if fail |
|---|---|---|---|
| G1 | User Stories tem persona attendee OU está explicitamente marcado "organizador/admin only" + Non-Goals lista | ▢ | PRD incompleto para UK público = P0 |
| G2 | NFR data retention tem GDPR UK retention (12mo default ou 6 anos contábil) | ▢ | P0 (risco regulatório ICO) |
| G3 | Moeda = GBP pence integer declarado explicitamente NFR + Data Model + Normalisation | ▢ | P0 (float = bug £ 0.01 em pagamentos) |
| G4 | RLS declarado: nova tabela tem ENABLE RLS + policies em Data Model + AC | ▢ | P0 (Flockr RLS mandatory em novas tabelas) |
| G5 | PII raw nunca logado declarado NFR observability | ▢ | P0 (LGPD/UK GDPR + PII rules) |
| G6 | Race/double click testado em AC (AC-4 style) | ▢ | P1 (usuários sofrem duplicação) |
| G7 | Role-based permission denied AC existe (AC-2 style) | ▢ | P0 (segurança por obscuridade) |
| G8 | Non-Goals tem pelo menos 2 bullets | ▢ | P1 (previne scope creep futuro) |
| G9 | Stripe/Resend/External failure mode declarado (retry + degrade ou hard-fail) | ▢ | P1 por external; P0 se money-movement |
| G10 | Open Questions P0 > 3? | ▢ | Se sim → antes de aprovar PRD, devemos fechar P0 primeiro. |

This table goes to the user in Portuguese, list of P0s if any, waiting for answers before PRD assembly.
