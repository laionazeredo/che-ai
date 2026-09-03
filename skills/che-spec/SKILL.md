---
name: "che-spec"
description: "Generate or validate a Che Execution Specification (SPEC). 4 inputs: existing spec file, ticket URL (Linear/ClickUp/GitHub), legacy-project PRD .md path, or inline brief. Produces 7 sections + machine-parsable YAML frontmatter, user-approved before save into $CHE_WORKSPACE_SHARED/spec_<slug>.md (DURABLE workspace area OUTSIDE user worktree code)."
---

# Che Spec Generator (SPEC)

> **SHARED REFERENCES (CANONICAL — NÃO DUPLICAR corpo aqui):**
> - Full contracts (precedence 1-18, DbC, BDD incremental, etc): `engineering-contracts` skill
> - Path resolution (WORKSPACE_NAME, WORKTREE_SLUG, CHE_WORKSPACE_SHARED, CHE_SESSION_DIR): `source "${CHE_HOME:-$HOME/.trae}/contracts/che_sessions_contract.sh"`, call `che_compute_paths WT SID CWD`
> - Worktree binding 2-LEVEL (Level1 registry, Level2 sessions dir): engineering-contracts §19

Produces **1 file per feature/bug/refactor:** a compact, agent-optimised spec (~60–120 lines, 7 sections). Replaces project-specific legacy PRD artifacts. Gate before scope capture in `/che-start` and standalone runnable via `/che-spec`.

---

## §0 PURPOSE & INTEGRATION

When called:
1. **From `/che-start` (embedded)**: runs AFTER binding §19 + ensure_dirs, BEFORE scope capture §1. User says which SPEC to use or generates new.
2. **Standalone** via `/che-spec`: runs independently; performs binding if needed, then generates or edits spec.

On completion this skill **returns to the caller** two values printed in the last 2 lines of the transcript:
- `SPEC_PATH=<absolute-path-to-spec>` — used by che-scrum-master
- `SPEC_STATUS=Approved|Draft` — only `Approved` unlocks subsequent execution in SM.

---

## §1 PREFLIGHT (Run FIRST)

Fail if any step fails. Stop before proceeding with user.

1. **Binding check:** Read `che_registry_path`, find LAST entry with the effective session id from `che_current_session_id` + `STATUS=BOUND`. If missing AND user did not provide `--worktree` → ASK for absolute worktree, perform full §19 binding (Level1 append + Level2 write + FRIENDLY_NAME prompt).
2. **Paths:**
   ```bash
   source "${CHE_HOME:-$HOME/.trae}/contracts/che_sessions_contract.sh"
   che_compute_paths "$WORKTREE_ROOT" "$(che_current_session_id)" "$PWD"
   che_ensure_session_dirs
   ```
3. **Slug:** If user passed `--slug`, use it as-is (sanitize to `[a-z0-9_-]+`). Otherwise derive from `ticket_ref` or `change_class+why`.

### §1.4 Feature Flag Provider Preflight Check (MANDATORY if risk_level ≥ medium)

> **Motivo ONDA4:** NÃO inventar feature flags do zero se o projeto não tiver infraestrutura definida a priori. Só perguntar ao usuário sobre flags SE um provider for detectado. Default fallback = rollback nativo da plataforma de deploy.

**GATILHO de execução (HARD RULE):**
- SE `risk_level === low` (frontmatter §HEAD L72) → **SKIP bloco INTEIRO, 0 linhas log, não pergunta nada ao usuário.**
- SE `risk_level === medium OU risk_level === high` → **EXECUTAR 3 passos ABAIXO, ordem fixa. NÃO pular nenhum passo.**

```bash
# DETECTED flag state inicial
FLAG_PROVIDER_DETECTED="none"
FLAG_PROVIDER_NAME=""

# PASSO 1 — SCAN WORKTREE feature libs conhecidas (maxdepth 5, evita node_modules)
echo "[PREFLIGHT §1.4 PASSO1/3] Scaneando worktree por libs feature flags..."
FLAG_LIBS_FOUND="$(cd "$WORKTREE_ROOT" && find . -maxdepth 5 -type f \( -iname 'feature.ts' -o -iname 'flags.ts' -o -iname '*.flags.ts' -o -iname 'feature-flags.ts' -o -iname 'feature.js' -o -iname 'flags.js' \) -not -path '*/node_modules/*' -not -path '*/.next/*' -not -path '*/dist/*' 2>/dev/null | tr '\n' ';')"
if [ -n "$FLAG_LIBS_FOUND" ] && [ "$FLAG_LIBS_FOUND" != ";" ]; then
  FLAG_PROVIDER_DETECTED="worktree_lib"
  FLAG_PROVIDER_NAME="worktree-files:${FLAG_LIBS_FOUND%;}"
  echo "[INFO §1.4] DETECTADO PASSO1: arquivos feature flags em worktree → pode recomendar flags se risco justificar."
fi

# PASSO 2 — SCAN ENV PATTERNS providers conhecidos (8 patterns canônicos)
if [ "$FLAG_PROVIDER_DETECTED" = "none" ]; then
  echo "[PREFLIGHT §1.4 PASSO2/3] Scaneando .env.example e afins por patterns provider feature flags..."
  ENV_CANDIDATES=".env.example .env.local.example .env.development.example .env.production.example .env"
  ENV_PATTERNS='^(export )?(FLAG_|FEATURE_FLAG_|LD_|UNLEASH_|STATSIG_|EDGE_CONFIG_|OPENFEATURE_|SPLITIO_)'
  FLAG_ENV_FOUND=""
  for envf in $ENV_CANDIDATES; do
    if [ -f "$WORKTREE_ROOT/$envf" ]; then
      MATCHES="$(grep -rE "$ENV_PATTERNS" "$WORKTREE_ROOT/$envf" 2>/dev/null | head -5 | tr '\n' ';')"
      if [ -n "$MATCHES" ]; then
        FLAG_ENV_FOUND="${FLAG_ENV_FOUND}${envf}:${MATCHES};"
      fi
    fi
  done
  if [ -n "$FLAG_ENV_FOUND" ]; then
    FLAG_PROVIDER_DETECTED="env_pattern"
    FLAG_PROVIDER_NAME="env-patterns:${FLAG_ENV_FOUND%;}"
    echo "[INFO §1.4] DETECTADO PASSO2: env pattern provider feature flags → pode recomendar flags."
  fi
fi

# PASSO 3 — PRODUCT CONTEXT FRONTMATTER feature_flag_provider: (Level 1.5 registry)
if [ "$FLAG_PROVIDER_DETECTED" = "none" ]; then
  echo "[PREFLIGHT §1.4 PASSO3/3] Verificando product_context.md frontmatter feature_flag_provider..."
  PC_FILE="$CHE_WORKSPACE_SHARED/projects/${PROJECT_SLUG:-default}/product_context.md"
  if [ -f "$PC_FILE" ]; then
    PC_FLAG_PROVIDER="$(grep -E '^feature_flag_provider:\s*' "$PC_FILE" | head -1 | sed -E 's/^feature_flag_provider:\s*//' | tr -d '"' | tr -d "'" | xargs || true)"
    if [ -n "$PC_FLAG_PROVIDER" ] && [ "$PC_FLAG_PROVIDER" != "" ] && [ "$PC_FLAG_PROVIDER" != "none" ] && [ "$PC_FLAG_PROVIDER" != "null" ]; then
      FLAG_PROVIDER_DETECTED="product_context"
      FLAG_PROVIDER_NAME="product_context:${PC_FLAG_PROVIDER}"
      echo "[INFO §1.4] DETECTADO PASSO3: provider declarado em product_context.md → pode recomendar flags."
    fi
  fi
fi
```

**BRANCH DE RESULTADOS (HARD POLÍTICA, NÃO NEGOCIÁVEL):**

| Caso | Condição | Ação no draft da SPEC |
|---|---|---|
| **A — QUALQUER DETECTADO** | `FLAG_PROVIDER_DETECTED != none` (qualquer passo 1, 2 OU 3 achou) | NADA MUDANÇA ESPECIAL. Fluxo normal §3 + §4. PODE recomendar feature flag em §3 Contracts / §5 Risks se risco justificar (medium/high). Não pergunta nada ao usuário sobre flags (automático). |
| **B — NENHUM DETECTADO + risk ≥ med/high** | `FLAG_PROVIDER_DETECTED = none` AND `risk_level ∈ {medium, high}` | **HARD RULE: NÃO PODE obrigar feature flag em NENHUMA seção da spec (§3 PRE/POST, §4 SbE, §5 Verification, §6 Risks).** INSERIR LINHA OBRIGATÓRIA no draft §3 CONTRACTS → PREconditions bloco (último bullet PRE): <br>`- PRE-FF: Feature flags NOT AVAILABLE (nenhum provider detectado preflight §1.4). Fallback rollback default = plataforma deploy nativa: <Vercel Instant Rollback <30s \| Railway redeploy \| Supabase branch revert \| manual>` <br>Adicionar nota em §5 VERIFICATION (seção "Rollback trigger" se existir, senão como último bullet): <br>`Rollback default usa deploy nativo da plataforma (feature flags indisponíveis nesta worktree — nenhum provider detectado preflight §1.4).` <br>NÃO pergunta ao usuário se quer usar flags. NÃO cria configuração de flag. |

**EXCEÇÃO ÚNICA PERMITIDA (override user VERBATIM):**
- ÚNICO jeito de contornar Branch B (forçar obrigatoriedade de flag SEM provider detectado) = usuário digitar ANTES do spec gerar o literal EXATO: **`EXPLICIT_OVERRIDE_FEATURE_FLAGS_FORCE`** seguido de justificativa 1-linha. Exemplo usuário:
  > `EXPLICIT_OVERRIDE_FEATURE_FLAGS_FORCE: vamos lançar essa feature crítica numa sexta 22h, vou criar lib flags manualmente agora mesmo nesta PR`
- Se usuário digitou o literal → salvar como decision.log: `che_append_decision_jsonl "SPEC_PREFLIGHT_OVERRIDE" "preflight=§1.4_feature_flags type=EXPLICIT_OVERRIDE_FEATURE_FLAGS_FORCE rationale=<1-linha user verbatim> risk_level=${risk_level}"`. Depois PODE obrigar flags em seções da spec normalmente. Se NÃO digitou literal → Branch B é HARD STOP, não há discussão.

---

## §2 SOURCE SELECTION (4 inputs)

Present choices when input arg is missing or ambiguous. First match wins, never fallback silently.

| # | Source | User provides | Action before draft |
|---|---|---|---|
| A | **Existing SPEC file** | File path OR pick from glob `$CHE_WORKSPACE_SHARED/spec_*.md` | Read it; if `status=Approved` → jump straight to §5 (approval). If Draft → proceed to §3 editing with the existing content pre-filled. |
| B | **Ticket URL** (Linear FLO-XXX, ClickUp, GitHub issue) | Full URL | 1. Try to extract title + description + status via MCP tools (`mcp_flockr-linear`, `mcp_laion-clickup`, `mcp_github`). If MCP fails → fall back to user-provided inline description. 2. Populate frontmatter `ticket_ref:` + `spec_id:` from slug. 3. Seed §1 WHY bullets from ticket description. 4. Seed §4 MUST ACs = 3 bullets if ticket has Acceptance Criteria field. |
| C | **Legacy PRD** (.md legado do projeto) | Absolute path to `.md` file | Parse with headings, map: `Problem / Background` → §1 WHY; `Goals` → §4 MUST; `Non-Goals` → §1 Non-goals; `Data Model / Migration` → §6 Hints; `Acceptance Criteria` → §4 MUST AC, each prefixed `GWT` verbatim; `Risk` → §5 Rollback trigger. If section missing → leave empty and prompt user to fill during §4 review. |
| D | **Inline brief** (short text 2–5 sentences) | User typed description or typed nothing at all → walk through interactive prompts 1-by-1 | Prompt for: change_class (feature|bug|refactor|perf|ops); 3 bullets §1 WHY; 3 sections §2 (Can Touch ≤ 10 files, Can Create, Cannot Touch ≤ 5 lines); 3 PRE + 3 POST + 2 INVARIANTS in §3; 3 MUST + 1 SHOULD + 1 MAY §4 ACs (each AC must include GWT + TEST_METHOD literal). Defaults: `estimated_files_max=15`, `estimated_max_lines_add=400`, `new_dependencies=[]`, `pii_touch=none`, `supabase_rls_touch=false`, `currency_gbp_pence=false`, `domain=engineering`, `flags=LANG_PT_CHECK=ENABLED`. |

---

## §3 SPEC DRAFT STRUCTURE (9 sections — SbE CENTRIC, canonical)

Write the draft in-memory first. File starts with YAML frontmatter, THEN 9 markdown sections (§1-§9). **§4 SbE is the MANDATORY CENTRAL SECTION** (behaviors observable, NOT implementation). Ordem fixa — NÃO reordenar.

### §HEAD — YAML Frontmatter (REQUIRED fields — validate all present)
```yaml
---
spec_id: <slug-sanitized-alphanum-dash-underscore>
ticket_ref: <"FLO-745" or "NONE">
worktree_root: <absolute-path>
change_class: feature|bug|refactor|perf|ops
domain: engineering                  # valores aceitos: engineering | product | ux | devops | copywriting | social | seo-analytics
                                      # default = engineering (retrocompat total com specs/sessões/skills antigas sem esse campo)
                                      # se != engineering → SM §0.3 auto-carrega domains/<domain>/profile.md + playbook.md
                                      # se != engineering → ship §0.9.5 executa gates obrigatórios playbook
risk_level: low|medium|high           # NOVO SbE. default = low. Se medium/high → gatilho §4.4 Mermaid obrigatório.
source_merge_order: [user_prompt, prd_file, linear_ticket, implementer_hints]   # NOVO SbE CANÔNICO. NÃO reordenar sem EXPLICIT_OVERRIDE + decision log.
status: Draft
estimated_files_max: <integer; default 15; hard stop per §15>
estimated_max_lines_add: <integer; default 400; trigger for gh-stack>
new_dependencies: [ ]
pii_touch: none|read-only|write
supabase_rls_touch: true|false
currency_gbp_pence: true|false
bound_agent_lang: default|pt-BR|en
flags: LANG_PT_CHECK=ENABLED[, RLS_MANDATORY=NO]
approver: ""
approved_at: ""
# Contadores SbE auto-calculados (VAL09-V10 validation cross-check) — opcional, preencher no final do draft:
b_count: 0                            # NOVO: quantidade de B-IDs na §4.2 Behavior Table (auto-count)
ab_count: 0                           # NOVO: quantidade de AB-IDs na §4.3 Anti-Behavior Table (auto-count)
erd_required: false                   # NOVO: gatilho ERD. true SE E SOMENTE SE: (a) cria entidade DB NOVA; (b) altera cardinalidade FK ON DELETE/UPDATE; (c) adiciona ≥3 campos com constraints UNIQUE/UK/CHECK.
mermaid_required: false               # NOVO: gatilho diagrams. true SE E SOMENTE SE: b_count>=8 OR atores_publicos>=3 OR risk_level in {medium, high}.
---
```

### §1 WHY — Problem Statement (max 5 bullets)
Header: `## §1 WHY (Problem Statement)`
- 3–5 bullets only. Example structure:
  - Current: <what breaks today, 1 line concrete>
  - Risk: <security or business impact or UX pain>
  - Goal: <outcome in 1 line>
  - Success metric: <curl / behavioral assertion>
  - Non-goals: <what this SPEC does NOT do>

### §2 SCOPE — Blast Radius (3 lists, each ≤ 10 items)
Header: `## §2 SCOPE BOUNDARIES & BLAST RADIUS`
Three subsections EXACTLY:
- `### ✅ CAN TOUCH (<=10 files literal paths or glob patterns)` — ≤10 entries
- `### ✅ CAN CREATE (<=8 files/folders)` — new files; include folder path only if empty dir creation required
- `### ❌ CANNOT TOUCH (under any circumstances)` — list paths or packages; last bullet always: `Any worktree other than bound <WORKTREE_ROOT> (§19 scissor)`
- Optional bullet: `### External services touched:` (list services touched or `None`)

### §3 CONTRACTS (DbC — PRE / POST / INVARIANTS)
Header: `## §3 CONTRACTS (Design by Contract)`
- `### PREconditions (before start)` — ≥2 bullets, ≤5. Examples: bound worktree valid; HEAD snapshot taken; no uncommitted on §2 files; env var X set.
- `### POSTconditions (after all tasks DONE — assertion-ready)` — ≥3 bullets, ≤8. Each bullet = a statement you can run a single test against; use `==`, `∈ {x,y}`, or plain assert verbs.
- `### INVARIANTS (never break, even temporarily)` — ≥1, ≤5. Last INV if empty add: `INV-<N>: Files listed in CANNOT TOUCH §2 remain byte-for-byte unchanged git diff.`

### §4 SPECIFICATION BY EXAMPLE (SbE — CENTRAL OBRIGATÓRIO)
Header: `## §4 SPECIFICATION BY EXAMPLE (SbE — Public Behaviors Observable)`

> **CANONICAL SOURCE MERGING ORDER quando construir as tabelas abaixo (não reordenar sem EXPLICIT_OVERRIDE + decision.log):**
>   1st HIGHEST — **User Prompt VERBATIM** atual desta sessão
>   2nd — **Legacy PRD (.md)** (se source = C)
>   3rd — **Ticket Linear / ClickUp / GitHub Acceptance Criteria BRUTOS** (ac → 1 B-pos + 1 AB-neg mínimo)
>   4th LOWEST — Implementer hints (só preenche lacunas NÃO conflitantes)
>
> No final do draft §4, SEMPRE pergunte ao usuário:
> > "Tem mais edge case NEGATIVO (AB-) ou POSITIVO (B-) que devo adicionar às tabelas? Principais lacunas: (listar 2-3 missing behaviors da categoria mais crítica do user prompt)."

#### §4.1 KEY RULES (R1..RN — máx 8)
Header: `### §4.1 KEY RULES (Non-negotiable invariants 1–8)`
- MÁXIMO 8 bullets. Derivado das fontes acima, NÃO de implementação.
- NOME curto único R1..RN + 1 frase ação + impacto negócio.
- Exemplos:
  - R1: Refunds SEMPRE usam Stripe `reverse_transfer=true, refund_application_fee=false` (destination charges invariant).
  - R2: Nenhum email bruto persistido em logs admin (PII convention).
  - R3: Duplo clique no botão Confirm Refund NUNCA cria 2 refund (idempotency key dedup).

#### §4.2 BEHAVIOR EXAMPLE TABLE (B-IDs positivos — máx 10, 1st verification anchor)
Header: `### §4.2 POSITIVE BEHAVIOR EXAMPLES (B-ID 1..≤10)`

**Tabela Markdown OBRIGATÓRIA. Cada coluna = NÃO VAZIA (exceto UI Selector quando Playwright não marcado).**
| B-ID | Given (Setup Concreto) | When (Ação Única Pública) | Then (Observable Public Behavior ONLY — sem palavras "correctly"/"works" — valores literais / HTTP codes / textos UI / side effects observáveis externos) | Test Layers [Unit ✅|Integ ✅|API-E2E ✅|Playwright ✅|Manual ✅] — marcar ✅ CAMADA CASO-A-CASO, NÃO obrigar todas | UI Selector Contract (só se Playwright ✅) — data-testid 3-parties `<domain>__<component>__<action>`, kebab duplo `__` | Confidence target % | Risks se OMITIR camada marcada ⚠️ |
|---|---|---|---|---|---|---|---|
| B-1 | Given booking_id=BK-123 exists, status=pending_payment, stripe_capture=succeeded, amount=2000p | When creator POST /api/bookings/:id/refund reason="Duplicate" | Then (HTTP 201 refund.id=RF-456 · booking.status=REFUNDED · customer.emailHash=sha256(..) recebe refundConfirmation template · Stripe dashboard refund.amount=2000 with reverse_transfer=true) | [✅Integ ✅API-E2E ✅Manual] | `creator__bookings-row__refund-btn--BK-123` + `refund__action-btn__confirm` | 98% | Sem Integ: omissão Stripe params causa webhook race → dupla dedução balance. Sem Manual: UX loading state falha visualmente em 3G. |
| B-2 | ... | ... | ... | [...✅] | `...` | ... | ... |

Rules enforcement desta tabela:
1. **MÁXIMO 10 B-IDs TOTAIS** (se mais gh-stack 2 PRs).
2. **Then coluna DEVE ser PÚBLICO OBSERVÁVEL:** status HTTP, UI texto literal, email tipo, Stripe/DB campo público. PROIBIDO Then: "o service chama método X internamente" (implementation bias).
3. **Test Layers coluna:** HONEYCOMB PYRAMID. CASO-A-CASO. Marque ✅ só camadas que realmente resolva o behavior. Regras padrão:
   - Algoritmo puro isolado (math, formatter, hash): só ✅Unit.
   - Query/mutation REST+tRPC+DB (no UI): ✅Integ + ✅API-E2E (máx 2 camadas).
   - UI componente interativo (botão, formulário, loading): ✅Playwright + ✅Manual (2 camadas).
   - Regra de negócio transfronteiriça (3+ serviços): ✅Unit + ✅Integ + ✅API-E2E (3 camadas).
4. **Risks if omitir coluna:** DESCREVA NEGÓCIO impacto (não "coverage cai"). Ex: "Dupla dedução Stripe Connect balance $2k".
5. **UI Selector Contract coluna:** Se Playwright=✅ → OBRIGATÓRIO pelo menos 2 ids por behavior (trigger action + result verify). **Gatilho enforcement G8 Category 8 code-review (ONDA1) contra fragilidade XPath/classes.**
6. **Mapping Ticket AC → B-ID:** Cada Acceptance Criteria do ticket Linear → 1 B-ID positivo + 1 AB- anti (abaixo §4.3). No final do draft, mostrar lista: `AC-T1 → B-3 + AB-2`.

#### §4.3 ANTI-BEHAVIOR EXAMPLE TABLE (AB-IDs negativos — MÍNIMO 33% DE B-IDs)
Header: `### §4.3 ANTI-BEHAVIOR EXAMPLES (AB-ID 1..≥ceil(B_COUNT/3))`

Tabela idêntica a §4.2, mas **Then = comportamento proibido que NUNCA deve acontecer.**
| AB-ID | Given (Setup IDENTICO a B-ID correspondente — MESMO Given) | When (Ação PERIGOSA / inválida / duplicada / race) | Then PROIBIDO (public observável — o que NÃO ACONTECE, com valores literais) | Test Layers obrigatórios (≥1 camada ✅ por AB) | UI Selector (se Playwright) | Confidence target % | Risks se OMITIR teste AB |
|---|---|---|---|---|---|---|---|
| AB-1 | Given BK-123 pending_payment capture=succeeded amount=2000p idempotency_key=IK-XYZ | When DOUBLE-POST /api/bookings/:id/refund (2x paralelo com MESMO idempotency_key) | Then (HTTP 200 idempotent replay SAME RF-456 · booking.status NÃO transita · Stripe refund_count=1 · balance 1 movimento apenas) | [✅Integ ✅API-E2E] | `refund__action-btn__confirm` (double click rate limit check) | 99,5% | Não testar → 5% dos refund em click duplo geram transfer reversal negativo e dispute. |
| AB-2 | ... | ... | Then NÃO... | [...✅] | ... | ... | ... |

Rules enforcement desta tabela:
1. **MÍNIMO 33% RATIO: `AB_COUNT ≥ ceil( B_COUNT / 3 )`** (validação V10). Ex: B=9→AB≥3; B=1→AB≥1; B=4→AB≥2.
2. **Given DEVE ser o MESMO setup de um B-ID positivo correspondente** (mesma linha Given). Prova que o sistema resiste ao lado ruim do happy path.
3. **When = ação que o usuário faria ERRADO ou atacante exploraria.** Double click, race condition, auth bypass, campo negativo, id já processado, etc.
4. **Then NÃO pode ser vago.** Valores literais. Then coluna SEMPRE começa com a palavra "Then NÃO" ou "Then (HTTP 4xx ... NÃO altera booking.status)".

#### §4.4 MERMAID DIAGRAMS (CONDICIONAL OBRIGATÓRIO — se gatilho disparado)
Header: `### §4.4 MERMAID DIAGRAMS (skip or mandatory — based on triggers)`

**Gatilho §4.4.1 + §4.4.2 OBRIGATÓRIOS SE E SOMENTE SE:**
`(B_COUNT >= 8) OR (COUNT(public_actors_distinct) >= 3) OR (risk_level in ["medium", "high"]) OR (frontmatter.mermaid_required = true)`
→ Se NENHUM: escrever exatamente `> ⚠️ Skipped (low complexity): B_COUNT=X<8 · public_actors=Y<3 · risk=low`.

**Gatilho §4.4.3 ERDiagram OBRIGATÓRIO SE E SOMENTE SE:**
`(nova_entidade_DB = true) OR (altera_cardinalidade_FK_ON_DELETE = true) OR (campos_novos_com_constraint_UNIQUE_CHECK >= 3) OR (frontmatter.erd_required = true)`

Mermaid rules HARD (parser crash se violar — validação V13):
- Shapes SÓ rectangle `ID["label"]`, diamond `ID{"?"}`, edge labels `|"txt"|`. NÃO stadium shapes.
- Quebras linha NO internamente aos labels SÓ `<br/>` HTML. NÃO literal `\n`.
- Atores SÓ PÚBLICOS (ex: Creator, Attendee, StripeWebhook, AdminUI). NÃO nome services interno (ex: RefundService, StripeClient). Proibido.
- TODOS nós e setas DEVEM ter referência `B-X` ou `AB-Y` no label. Ex: `Creator["Creator (B-1, B-2)"]`.

Sub-seções se gatilho disparar:
- **§4.4.1 sequenceDiagram** — Ordem atores e mensagens. Cada mensagem = B-ID ou AB-ID.
- **§4.4.2 flowchart TD** — Branches: (a) Happy path solid edge; (b) Sad/Error path dashed edge; (c) Rollback edge `--ROLLBACK-->` tracejado vermelho label. Nós = B-AB-IDs.
- **§4.4.3 erDiagram** (se ERD gatilho) — Cardinalidade Mermaid oficial: `| = exactly 1; o| = 0 or 1; }o = 0 or N; }| = 1 or N`. Cada FK ou campo novo com B-ID correspondente no comment. Constraints UK/CHECK/UNIQUE listadas explicitamente com o número B-ID do behavior que a usa.

### §5 VERIFICATION MATRIX (Bilateral B-ID ↔ Test File ↔ Evidence)
Header: `## §5 VERIFICATION MATRIX (Bilateral — B → Test → B)`

> **Purpose:** TODO checklist vivo que o che atualiza AUTOMATICAMENTE em cada loop do SM/Developer/QA.
> **Ancoras bilateral:** (1) Spec §4 B-ID → (2) Comentário `// @ac B-X` 1ª linha dentro do `it()`/`test()` → (3) Resultado/evidence sha256.
> **Scope-checker CHECK2 (ONDA2 próximo bloco) valida o reverso: (2) → (1) + (3).**

Tabela Markdown OBRIGATÓRIA (B-IDs first, depois AB-IDs abaixo):
| Anchor (B or AB) | Status (Planned|Written|Passed|Failed|Skipped) | Test file ABSOLUTE PATH (real path dentro worktree bound) | Evidence sha256 (hash stdout/err ou screenshot png hash) | QA Owner Assigned | Notes |
|---|---|---|---|---|---|
| B-1 | Planned | `packages/platform/server/__tests__/e2e/refundFlow.api.test.ts` L:78-111 | | Developer (SM) | // @ac B-3 | @ticket FLO-513 anchor |
| B-2 | Planned | ... | ... | ... | ... |
| AB-1 | Planned | `packages/platform/server/__tests__/integration/refundIdempotency.integ.test.ts` | | QA | Double click — Playwright extra step após integ |
| AB-2 | ... | ... | ... | ... | ... |

Atualização AUTOMÁTICA desta matriz EM CADA LOOP:
- Developer termina task → atualiza `Status=Written` + `Test file path`.
- QA run → atualiza `Status=Passed|Failed|Skipped` + append Evidence SHA256 (gerar via `sha256sum stdout.log | cut -d' ' -f1`).
- Failed → nova linha Notes "Reproduce: command X".
- **G5 Regression Location (linha Notes OBRIGATÓRIA para testes regression/repro lock):**
  Notes também deve indicar explicitamente **LOCATION do arquivo regression:
  - DEFAULT: ✅ `[colocated na pasta da feature / domínio — @ticket FLO-123` (regra padrão).
  - EXCEÇÃO (apenas se cross-cutting ≥4 domínios / infra pura): ⚠️ `[tests/regression/FLO-123--refund-idempotency.test.ts] — EXPLICIT_OVERRIDE_G5_REGRESSION_FOLDER decisions.log entry: auth+billing+notification+db ≥4 domínios — justificativa 1-linha`. Se o teste for o testes está em tests/regression com ticket ID no nome arquivo SEM entrada Notes vazia → scope-checker CHECK2 bilateral marca warning SCOPE_score -2 penalty).

### §6 MANUAL SMOKE TEST PLAN (Staging + Prod HUMAN — OBRIGATÓRIO SEMPRE)
Header: `## §6 MANUAL SMOKE TEST PLAN (HUMAN — Staging + Prod)`

> **User requirement VERBATIM: "Além dos testes e2e, devemos ter um plano de testes manual ... também deve ser pensado desde o inicio o teste manual quando for pra produção."**
> Mínimo 3 passos STAGING + 2 passos PROD.

#### §6.1 Ambiente STAGING (post-deploy pre-PR merge — 3..8 steps)
| Step # | Role (Creator|Attendee|Admin|Staff Scanner) | Ação Manual Concreta 1-clique / 1-tela | Expected Result (literal, public observável — matches Then de B-ID correspondente) | Anchor B-ID |
|---|---|---|---|---|
| S1 | Creator | Login staging; navegar Bookings → linha BK-123 → botão Refund → modal → Confirm. | (1) Toast verde "Refund RF-456 created"; (2) Status da linha → "Refunded"; (3) Email staging inbox → assunto "Your refund is on its way". | B-1 |
| S2 | ... | ... | ... | B-2 |
| S3 | Creator | Repetir Step S1 DUPLO CLIQUE rápido no botão Confirm | (1) Apenas 1 toast; (2) 1 entrada Refunds history; (3) Stripe dashboard staging → 1 refund only. | AB-1 |

#### §6.2 Ambiente PROD (post deploy live — 2..5 steps MÍNIMO NON-DESTRUCTIVE)
| Step # | Role | Ação Manual SEGURA (NÃO tocar dado produção real — usar dummy canary event se possível) | Expected Result Canary | Anchor B-ID |
|---|---|---|---|---|
| P1 | Admin | Acessar `/admin/health` → aba "Refund health check" (criar se não existir) → Executar canary refund de 0.01 GBP em sandbox connected account CA-TEST-ONLY. | Canary result: Stripe reverse_transfer=true; response 200; DB canary_refund_audit table 1 row. | B-1 |
| P2 | Admin | Visualizar Logs produção últimos 15 min → filtro `service=refund` | Nenhum ERROR / stacktrace após deploy. | B-4 |

#### §6.3 UI ONLY Extra Steps (se Playwright marcado em qualquer B-ID OU risk≥medium)
→ Se gatilho falso → escrever: `> ⚠️ Skipped: nenhum behavior com Playwright layer AND risk=low`.
→ Se gatilho verdadeiro → adicionar tabela steps UI cross-browser (Chrome/Firefox/Safari iOS 17):
| Step | Device/Browser | Ação | Expected UI visual | Anchor |
|---|---|---|---|---|
| UI-1 | Chrome Desktop 128, 125% zoom | 3G throttled. Confirm Refund → loading spinner → toast. | Spinner aparece ≥500ms ≤2s. Toast verde text match literal. Sem layout shift. | B-1 loading. |

### §7 IMPLEMENTATION HINTS (opt-in, only if re-use exists or gotchas — 2..5 bullets MAX)
Header: `## §7 IMPLEMENTATION HINTS (Optional — reference existing code only)`
- Bullet 1: Reference existing function/class/commit hash or existing pattern from graphify-out community hub ou `packages/platform/server/providers/stripe/StripeClient.ts createRefund` params.
- Bullet 2: Gotcha runtime. Ex: "Vercel edge runtime: NÃO usar setImmediate para envio email; usar queues/await direto ou webhook."
- NÃO adicionar implementação sketch aqui → seções §4 SbE já definem comportamento público. Isso é só acelerador de contexto.


---

## §4 VALIDATION PASS (auto-run on draft — SbE rules V9..V15 NEW)

Reject draft and loop back to §2 source if ANY check fails. Run in order.

### Legacy baseline checks (V1-V8)
1. **V1** YAML frontmatter all REQUIRED keys present; parseable as YAML.
2. **V2** `estimated_files_max ≤ 20` (§15 engineering-contracts KISS); if >20 → force user to reduce scope or trigger gh-stack immediately.
3. **V3** §1 WHY bullets ≤ 5.
4. **V4** §2 CAN TOUCH count ≤ 10 literal files or glob entries.
5. **V5** §3 ≥3 POSTconditions, ≥1 INVARIANT.
6. **V6** (legacy supercedido por V9-V15 mas ainda run para specs antigas sem SbE) → se spec NÃO contém header `## §4 SPECIFICATION BY EXAMPLE` ainda: §4 ACs ≥3 MUST, cada bullet contém GIVEN/WHEN/THEN/TEST literal. Else SKIP this check gracefully (SbE drafts NÃO usam mais MoSCoW ACs).
7. **V7** (legacy, skip se SbE draft) §5 rollback trigger = exactly 1 trigger sentence, non-empty.
8. **V8** (optional, always run se domain preenchido diferente default) → `domain:` MUST estar no EXATO 7-slugs enum canônico: `engineering | product | ux | devops | copywriting | social | seo-analytics`. Se typo/fora enum → **REJECT draft with clear msg**: "Campo `domain: <valor_invalido>` inválido. Valores aceitos: engineering | product | ux | devops | copywriting | social | seo-analytics. Default omissão = engineering (retrocompat). Corrija frontmatter ou remova o campo. Default é engineering."

### SbE MANDATORY checks (V9-V15 — run SOMENTE se header `## §4 SPECIFICATION BY EXAMPLE` existe no draft. Hoje = SEMPRE, porque SbE = default.)
9.  **V9 B-IDs max 10:** Contar linhas na §4.2 POSITIVE BEHAVIOR TABLE cuja 1ª coluna começa exatamente com `B-` e tem dígitos após (`B-1`, `B-10`). `B_COUNT = COUNT`. Se `B_COUNT > 10` → REJECT: "Positive behaviors (B-IDs) = $B_COUNT. MÁXIMO permitido = 10. Reduza scope ou use gh-stack para 2 PRs independentes (ver engineering-contracts §15 gh-stack multi-PR reference)."
10. **V10 Anti-behavior ratio min 33%:** Contar AB-IDs na §4.3 ANTI-BEHAVIOR TABLE → `AB_COUNT = COUNT`. Calcular `EXPECTED_AB_MIN = ceil(B_COUNT / 3)`. Se `AB_COUNT < EXPECTED_AB_MIN` → REJECT: "Anti-behaviors (AB-IDs) faltantes. B_COUNT=$B_COUNT, AB_COUNT=$AB_COUNT, MÍNIMO ESPERADO = ceil($B_COUNT/3) = $EXPECTED_AB_MIN. Adicione pelo menos ($EXPECTED_AB_MIN - $AB_COUNT) AB- negativos (race/edge/inválido/ataque) na tabela §4.3."
11. **V11 Cada B-ID tem ≥1 Test Layer marcado ✅:** Parse cada linha B- na tabela §4.2 coluna "Test Layers" — se NÃO contém caractere literal `✅` pelo menos 1 vez → REJECT: "B-XX coluna Test Layers não tem NENHUMA camada marcada ✅ (Unit/Integ/API-E2E/Playwright/Manual). Marque pelo menos 1 camada CASO-A-CASO (honeycomb pyramid; não obrigue todas)."
12. **V12 UI Selector Contract regex validation:** Para cada linha B-ID onde coluna "Test Layers" CONTÉM literal `Playwright` → extrair ids da coluna "UI Selector Contract". Cada data-testid DEVE bater REGEX canônico Category 8 G8.3: `^[a-z0-9][a-z0-9-]*__[a-z0-9][a-z0-9-]*__[a-z0-9][a-z0-9-]*(--[a-z0-9][a-z0-9-]*)?$`. Se NÃO bater → REJECT: "B-XX data-testid=`<id>` fora convenção 3-partes `<domain>__<component>__<action>[--unique-suffix]`. Regex esperado: `^[a-z0-9-]+__[a-z0-9-]+__[a-z0-9-]+(--[a-z0-9-]+)?$`."
13. **V13 Mermaid diagrams trigger compliance:**
    a. Calcular GATILHO_MERMAID = `(B_COUNT >= 8) OR (risk_level == "medium") OR (risk_level == "high") OR (mermaid_required == true) OR (atores_publicos_distintos >= 3)`.
    b. Se GATILHO_MERMAID == TRUE → validar que o draft CONTÉM os 2 headings exatos: `### §4.4.1 sequenceDiagram` E `### §4.4.2 flowchart TD`. Se faltar QUALQUER um → REJECT: "Gatilho Mermaid disparado (B=$B_COUNT, risk=$risk_level). §4.4.1 sequenceDiagram e §4.4.2 flowchart TD AMBOS obrigatórios. Falta X."
    c. Calcular GATILHO_ERD = `(erd_required == true) OR (nova_entidade_DB detectada pela palavra CREATE TABLE/ TypeORM Entity() nova em §2 CAN CREATE) OR (campos_novos >= 3 palavras UNIQUE|CHECK|UK em §2 SCOPE)`.
    d. Se GATILHO_ERD == TRUE → validar que o draft CONTÉM heading exato `### §4.4.3 erDiagram`. Se faltar → REJECT: "Gatilho ERD disparado (nova entidade DB ou alteração FK/cardinalidade ou ≥3 campos constraints). §4.4.3 erDiagram obrigatório."
    e. (Anti-crash parser Mermaid) Se §4.4 contiver mermaid code blocks: validar que NENHUM nó contém shapes stadium `[/` ou `([` ou `\]/` ou `)]`. Se tiver stadium shape → WARNING (não fatal mas recomenda correção antes de Approved): "Warning: Mermaid stadium shapes ( [/label/] ou ([label]) ) colidem com chars ()/ no label texto → parser crash 10.x+ Mermaid. Trocar por rectangle quoted `ID[\"label\"]`."
14. **V14 §6 Manual Smoke Plan staging minimum 3 steps e prod minimum 2 steps:** Contar linhas da tabela §6.1 Staging coluna Step # com S-1,S-2,S-3 → se `< 3 passos` → REJECT: "Manual Smoke Plan STAGING (§6.1) tem $N passos. MÍNIMO 3 passos obrigatórios." Contar passos §6.2 Prod P-1,P-2 → se `< 2 passos` → REJECT: "Manual Smoke Plan PROD (§6.2) tem $N passos. MÍNIMO 2 passos obrigatórios NON-DESTRUCTIVE."
15. **V15 Frontmatter counters match actual tables:** Se b_count ou ab_count estão preenchidos no YAML (≠ 0 ou empty) → validar `frontmatter.b_count == B_COUNT real da tabela §4.2` AND `frontmatter.ab_count == AB_COUNT real da tabela §4.3`. Se divergir → WARNING não fatal: "Warning: frontmatter.b_count=$front ab_count=$front != tabela real B=$realB AB=$realAB. Auto-fix before Approved."

### Cross-ref scope-checker CHECK2 bilateral (ONDA2 próximo bloco)
When this VALIDATION PASS runs GREEN (all pass), the che also prints a 1-line footer:
> `SbE spec valid: B=$B_COUNT AB=$AB_COUNT AB_ratio=$RATIO% Mermaid=$TRIG ERD=$ERD_TRIG.`
This line is parsed by `che-scope-checker` CHECK2 (ONDA2) before performing bilateral B-ID ↔ test file cross-validation.

---

## §5 APPROVAL LOOP (1 main pass, 1 edit pass MAX — KISS)

1. **Show draft** to user as compact markdown, WITH a legend at the top saying "Draft SPEC. Reply A = Approve as-is. Reply B = adjust <tell what to change>."
2. **If A (Approved verbatim):**
   - Update frontmatter → `status: Approved`
   - Set `approver: "user-verbatim: A"`
   - Set `approved_at: <ISO timestamp local tz>`
   - Jump to §6 SAVE.
3. **If B (adjust X):**
   - Apply edits literally to the sections user indicated (no scope creep beyond what the user typed).
   - Re-run §4 VALIDATION.
   - Re-show ONE TIME only.
   - User now either Approves → update frontmatter Approved → SAVE. OR says "more edits" → tell user to re-run `/che-spec` fresh (avoid infinite loops).
4. **If user says "Cancel":** Write Draft (no Approved flag) → SAVE anyway for future work. Print warning: `SPEC_STATUS=Draft (not Approved — che-start will re-prompt when you run it)`. End.

---

## §6 SAVE (atomic write via contrato helpers)

1. **Final sanitize slug:** `slug = frontmatter.spec_id` sanitized `[^a-zA-Z0-9_-] → -`.
2. **Construir path ÚNICO via `che_output_path` (NUNCA manual):**
   ```bash
   # type=spec → subpasta specs/ (WORKSPACE_SHARED, durável multi-session)
   # related_id = slug spec → agrupa versões futuras v2/v3 se houver
   # scope = workspace → DURÁVEL
   SPEC_FINAL_PATH="$(che_output_path "spec" "spec" "${slug}" "workspace" "md")"
   ```
   Resultado exemplo: `$CHE_WORKSPACE_SHARED/specs/feat-refund-pipeline/20260902-120000-spec.md`
   → Timestamp no prefix: se gerar v2 depois, `20260902-150000-spec.md` ordena DEPOIS automaticamente.
3. **Check existing overwrite:** If file already exists AND status in existing is Approved → ask "Overwrite Approved spec? Yes/No" before writing. Yes = overwrite. No = append suffix `-v2`, `-v3` to slug until unused.
4. **Escrever EXCLUSIVAMENTE via atomic write helper:**
   ```bash
   # NÃO escreva .tmp manual. Use o helper canônico tmp → mv atômico:
   cat <<'SPEC_EOF' | che_write_file_atomic "$SPEC_FINAL_PATH"
   ---
   # YAML frontmatter completo aqui
   ---
   # 7 seções do SPEC aqui
   SPEC_EOF
   ```
   (O helper já roda `che_assert_outside_worktree` automaticamente antes do write.)
5. **Append decision entry via `che_append_decision_jsonl` (NÃO construa path nem formate JSON manualmente):**
   ```bash
   # o helper decisions já garante path fora worktree + atomic append
   che_append_decision_jsonl "SPEC" "${slug} ${status} saved. Approver=${approver}"
   ```

---

## §7 RETURN VALUES

Print LAST 2 lines of transcript in a fenced code block EXACTLY:

```
SPEC_PATH=<absolute path of saved spec, no quotes>
SPEC_STATUS=Approved|Draft
```

Scrum Master §0.5 parses these 2 lines to proceed.
