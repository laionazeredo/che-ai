---
name: "che-scope-checker"
description: "6-check scope audit persona (CANONICAL 2026-09: 4 checks legacy + 2 new). From PRD/ticket/task-graph + GitHub PR OR local worktree, validates: (1) every acceptance criteria / item DELIVERED in diff with file evidence, (2) unit/e2e tests exist matching behavioral names for expected behavior, (3) required documentation is updated (AGENTS, README, runbooks, CLAUDE), (4) any NEW env var has corresponding declaration in infra/env parser (zod schema, .env.example, terraform/railway/vercel vars), (5) LEAN/KISS/YAGNI — overengineering scanner 12 categorias L1-L12 + justificador de escopo, (6) SCORE FINAL 0-10 media geometrica scope x lean. Invoked by /che-scope-check or as SHIP gate before PR draft (che-ship §0.9 GATES order 1)."
---

# Che — Scope Checker (6-check audit persona)

> **SHARED REFERENCES (CANONICAL — NÃO DUPLICAR corpo aqui):**
> - GitHub CLI gh auth + PR diff fetch: `../che-code-review/references/_shared_checklists/GITHUB_CLI_COMMON.md`
> - Stack auto-detection (test runners, doc files, env parsers): `../che-qa/references/_shared_checklists/NX_PNPM_COMMON.md`
> - Security/PII/RLS checklist: `../che-code-review/references/_shared_checklists/SECURITY_PII_COMMON.md`

Auditor persona com **2 modos mutuamente exclusivos** (escolher EXATAMENTE 1). **Sempre retorna relatório estruturado com evidence por linha e nomes REGRA7.9 comportamento observável.**

---

## 0. Preconditions — 2 modos + binding check

### 0.1 WORKTREE SESSION BINDING CHECK (engineering-contracts §19, NÃO NEGOCIÁVEL)

Run ANTES de decidir o modo.

1. **Ler Level1 Global Index PRIMEIRO:** Read `che_registry_path`. Find LAST `STATUS=BOUND` entry using the effective session id from `che_current_session_id`. Use its `WORKTREE_ROOT` como sessão default.
2. **Mode B mismatch check:** user passed `--worktree <path>` E Level1 registry WORKTREE_ROOT existe AND é DIFERENTE → BLOCK. Perguntar: "Scope check pedido em `<path>` mas binding Level1 global BOUND em `<y>`. Opções: (A) usa `<path>` e override binding temporariamente para este audit, (B) switch binding primeiro, (C) cancelar audit." **NUNCA silent override.**
3. **Mode A PR URL conflito binding:** PR branch = worktree branch de algum binding já existente e user também passou `--worktree` apontando outro → BLOCK. Perguntar qual é o alvo.

### 0.2 Como decidir qual modo

- Se user fornece **BOTH PR URL E --worktree** → prefer Mode A (PR URL). `--worktree` vira optional local path para salvar relatório em disco só.
- Se user fornece **`--worktree <path>` (ou indicador worktree explícito) E NENHUMA PR URL** → **FORCE Mode B (Worktree local)**. NÃO pedir PR URL.

---

### 0.3 Scope Sources obrigatórios (1+ mínimo; combinação permitida; ordem de prioridade)

NENHUM scope source = ASK user. Não procede sem escopo.

| Ordem | Fonte | Como extrair ACs/items |
|---|---|---|
| 1 | `--prd=/abs/path/prd.md` | Headings `## Acceptance Criteria`, `## ACs`, `## Goal`, `## Out of Scope`, bullets `* [ ]`, numbered list. |
| 2 | `--ticket=<Linear/Jira URL>` | Linear GraphQL `state,description,acceptanceCriteria,estimate,project,identifier,title,relationship:`; Jira REST `fields.summary,fields.description,fields.customfield_*_criteria`. |
| 3 | `--task-graph=/abs/path/task_graph.md` | Todos os `## Task Tn` + status lines `[COMPLETED]` + subtasks bullets. |
| 4 | `--scope="texto livre"` | Split por bullets, numbered, ou vírgulas se lista inline. |
| 5 | `PR body` (Modo A só) | Extrai automaticamente seções de ACs, todos `- [ ]` / `- [x]`, headings. |

Extração produz array plana `AC[]` = `{id: string, text: string, area?: string, oos?: boolean}`. OOS items = marcados explicitamente como out-of-scope NÃO contam como missing no relatório.

### 0.4 SbE Spec AUTO-DETECTION (ONDA2 bilateral mode — se detectar, roda CHECK 2 EXTENSION §3.5 OBRIGATÓRIO)

Run DEPOIS de §0.3 Scope Sources, ANTES de §1 Gather context.

**Modos de entrada para SbE bilateral (qualquer um 1 = ativa extensão):**
1. User fornece flag explícito: `--spec=/absolute/path/to/approved_spec.md`
2. Scope Source (PRD file / PR body / task graph) CONTÉM o heading literal `## §4 SPECIFICATION BY EXAMPLE` ou `## §4.2 POSITIVE BEHAVIOR EXAMPLES`
3. Auto-scan workspace_shared specs: list `$CHE_WORKSPACE_SHARED/specs/<slug-matching-ticket-id>/*spec.md` files com `status: Approved` no frontmatter → se ENCONTRAR 1 match, pergunta user: "Detectei Approved spec SbE em <path>. Usar como escopo bilateral B-ID ↔ test ↔ diagrams? (Y/n)". Default = Sim.

**Se SbE spec detectado:**
- Set `SBE_SPEC_PATH = <absolute path>`
- Parse frontmatter YAML: extrair `risk_level`, `b_count`, `ab_count`, `erd_required`, `mermaid_required`.
- Parse §4.2 Behavior Table: produz `SBE_BEHAVIORS[] = { b_id: "B-1", given: "...", when: "...", then_obs: "...", playwright_layer_checked: true|false, ui_selectors: ["id1","id2"]}`
- Parse §4.3 Anti-Behavior Table: produz `SBE_ANTI[] = { ab_id: "AB-1", ... }`
- Parse §4.4 Mermaid (se existir): produz `SBE_MERMAID_BIDS = set()` contendo todos `B-\d+` e `AB-\d+` extraídos de nodes/edges dos 3 diagrams.
- **Variável de controle:** `SBE_EXTENSION_ENABLED = true`. Se nenhum método acima → `false` e pula §3.5 (modo legacy).


---

## 1. Gather context — modo dependente

### Mode A (GitHub PR) → use `gh` CLI (navegador NÃO)

```bash
gh pr view <PR_URL> --json \
  number,title,body,baseRefName,headRefName,additions,deletions,changedFiles,files
```

Record:
- `PR_ID`, `BASE_BRANCH`, `HEAD_BRANCH`
- `changedFiles_count`, diff stat
- `FILES[]` = lista arquivos alterados + status (added/modified/deleted)
- `PR body` texto → scope source #5 acima

Full diff patches:
```bash
gh pr diff <PR_URL> > /tmp/pr-<id>-full.diff
```

### Mode B (Worktree local) → git commands (no gh / no network)

Todos os comandos rodam DENTRO de `<WORKTREE_ROOT>`. Nunca saem.

```bash
# Base branch detection (auto)
git remote show origin | grep 'HEAD branch' | awk '{print $NF}'  # default
# Se ambíguo (main e dev existem e diff tem ambos) → ASK user.

# Captura modified/staged/untracked files
git status --short                              # summary
git diff "$BASE_BRANCH"..HEAD --unified=3       # vs base (committed)
git diff --cached --unified=3                   # staged
git diff --unified=3                             # unstaged
cat /tmp/wt-full.diff                            # concat todos acima em 1 patch cumulativo
```

Modification area empty check (WARN, não FAIL): se 0 arquivos modificados vs base, perguntar "continuar auditando todo o repo vs scope ou parar?"

---

## 2. CHECK 1 — 🔍 Entrega do ESCOPO COMPLETO (toda AC tem file evidence)

### Passo 2.1 — Parsear ACs e keywords

Para cada `AC[i]`:
1. Nome canônico REGRA7.9: `entrega_de_escopo_completo_para_ac_<slug>`
2. Extrair **keywords comportamentais** (substantivos + verbos de negócio) e **arquivos/Áreas esperadas** (heurísticas: "auth" → `packages/auth/**`, "dashboard" → `**/dashboard/**`, "stripe" → arquivos stripe*, "migration" → `**/migrations/**`, "README" → `README.md`, "AGENTS" → `**/AGENTS.md`).

### Passo 2.2 — Mapear AC → arquivo(s) diff

Para cada AC[i]:
- Fazer match `keywords comportamentais` contra `diff patch texto completo` + paths alterados.
- **Match forte:** path `**/user-auth/**` alterado + palavras `login | session | JWT` aparecem no patch → 🟢 DELIVERED
- **Match médio:** path parece certo mas conteúdo não tem keyword → 🟡 PARCIAL (explicar o que faltou de evidence)
- **Match fraco / nenhum:** NADA no diff → 🔴 MISSING (apontar qual seria área + onde o código deveria estar)
- **OOS items:** ⚪ SKIPPED (contam para informação, não para verdict)

### Passo 2.3 — Report format por AC

Tabela 4 colunas, NOMES REGRA7.9:

| AC ID | Regra comportamental | Verdict | Evidence (file path:lines) |
|---|---|---|---|
| AC-1 | `entrega_de_escopo_completo_para_ac_login_google_oauth` | 🟢 DELIVERED | [auth.ts#L42-L88](file:///...) + [route.ts#L1-L40](file:///...) |
| AC-2 | `entrega_de_escopo_completo_para_ac_refund_stripe_connect` | 🟡 PARCIAL | [refund.ts#L20-L50](file:///...) implementa api mas **faltou** chamada connect account destination |
| AC-3 | `entrega_de_escopo_completo_para_ac_qrcode_offline_scan` | 🔴 MISSING | Nenhum arquivo em `packages/scanner/**` alterado. Esperado alteração em `scanner/lib/scan.ts` ou `scanner/app/scan/page.tsx`. |

---

## 3. CHECK 2 — 🧪 Cobertura de TESTES (unit/e2e cobrem comportamento esperado)

### Passo 3.1 — Auto-detect stack de teste

Mesma tabela do che-qa §1.4. Detecta Vitest, Jest, Playwright, Cypress, pytest, cargo test, go test etc.

### Passo 3.2 — Detectar arquivos de teste existentes NO DIFF

Do patch cumulativo, filtrar:
- Files matching: `*.test.*`, `*.spec.*`, `**/__tests__/**`, `**/e2e/**`, `**/playwright/**/*.spec.*`, `*_test.go`, `tests/**/*.py`
- + NÃO testes, mas SUT (system under test) arquivos correspondentes.

### Passo 3.3 — Mapear AC comportamental → describe()/it() behavioral names

REGRA7.9: Nomes de suites/testes DEVEM ser comportamento observável. Nomes ruins (FLO-123, test(), it1, shouldWork) não contam como evidence coverage.

**🔴 HARD RULE — INVERSÃO PROIBIDA: NÃO PENALIZE títulos SEM task-id:**
> ❌ **ERRADO:** "Título não tem FLO-714 como prefixo → evidence inválida / desconta pontos". **ISTO É UMA REGRESSÃO.**
> ✅ **CORRETO:** Título descreve comportamento observável + NÃO tem FLO/T/AC na STRING → BOM, compliant, conta como evidence.
>
> **O que INVALIDA evidence (ruim):** a STRING do título contém anti-padrões `FLO-\d+` / `Task? T\d+` / `AC\d+` / `§\d+` / `SPEC_XXX`.
> **O que VALIDA evidence (bom):** título contém keywords da AC (verbs + nouns do comportamento) + não tem IDs. Traceabilidade via comentário `// @ac 2.1 | @ticket FLO-732` DENTRO do bloco = também BOM e não penaliza.

Raciocínio por AC:
- Para cada AC comportamental tipo "usuário consegue aplicar refund stripe connect" → procurar nos testes strings como: `refund`, `stripe connect`, `connected account`, `refund succeeded`, `refund failed`
- Se descreve comportamento = 🟢 TESTED (mesmo que não mencione FLO/T/AC — é o comportamento DESEJADO)
- Se tem arquivo de teste pro módulo MAS nenhum caso acerta keyword da AC → 🟡 PARCIAL (quais testes existem vs falta qual comportamento específico)
- Se SUT foi alterado e ZERO arquivo de teste alterado pra área → 🔴 NOT TESTED (qual behavior, qual file test criar)

### Passo 3.4 — Report format

| Área / AC | Regra comportamental | Verdict | Evidence test (path:lines) |
|---|---|---|---|
| AC-1 refund | `cobertura_de_teste_unitario_ou_e2e_para_refund_connect_account` | 🟢 TESTED | [refund.test.ts#L102-L145](file:///...) it(`refunds_connected_account_destination_correctly`) |
| AC-2 qrcode offline | `cobertura_de_teste_unitario_ou_e2e_para_qrcode_offline_scan` | 🟡 PARCIAL | [scanner/scanner.test.ts#L5-L18](file:///…) suite existe, só happy path online. **Faltou** caso offline + cache fallback. |
| AC-3 login google | `cobertura_de_teste_unitario_ou_e2e_para_login_google_oauth_redirect` | 🔴 NOT TESTED | `packages/auth/src/google.ts` alterado, NENHUM `*.test.*` em `packages/auth/**` tocado. Criar `google-login.spec.ts` com casos: redirect_uri, state param, token exchange. |

### Passo 3.5 — ⚡ CHECK 2 EXTENSION SbE BILATERAL ENFORCEMENT (3 sub-checks) — SÓ RODA SE `SBE_EXTENSION_ENABLED = true` (§0.4)

> **Pilar ONDA2 bilateral verification loop:** Spec §4 Behavior → Test anchor → Evidence SHA → Spec §5 atualizada. Scope-checker valida o loop reverso também (qual B-coverage vs realidade).

**3.5.1 Bilateral 1/3 — Anchor @ac B-X → it() body coverage (traça cada B-ID → arquivo de teste real)**

Regra de varredura:
1. **Regex de detecção anchor (exato G7.3 Category7 che-code-review):** `^\/\/\s*@(ac|ticket|task|bug)\s+(B-\d+|FLO-\d+|[A-Z]+-\d+)` — **DEVE ser a PRIMEIRA LINHA DENTRO do bloco `it(...) { ... }` ou `test(...) { ... }`**. Fora do bloco = NÃO conta como evidence bilateral (pode ser comentário casual).
2. **Universo scan:** TODOS arquivos de teste detectados em §3.2 (test/spec/__tests__/e2e/playwright files do diff) + SUT correspondentes se tiverem embed tests. NÃO scan o repo inteiro — só diff atual (blast radius).
3. **Cálculo coverage anchor:**
   ```
   B_COUNT_SPEC = len(SBE_BEHAVIORS[])           // §4.2 tabela real
   B_COVERED_BY_ANCHOR = count(SBE_BEHAVIORS.b_id ∋ aparece em pelo menos 1 match regex)
   BILATERAL_ANCHOR_COVERAGE_PCT = B_COVERED_BY_ANCHOR ÷ max(1, B_COUNT_SPEC) × 100
   ```
4. **Severidade / Verdict:**
   - **🔴 BLOCK (hard stop):** BILATERAL_ANCHOR_COVERAGE_PCT = 0% → NENHUM comportamento SbE tem anchor bilateral. **Exigir EXPLICIT_OVERRIDE_BILATERAL_SKIP com justificativa + decision.log entry.**
   - **🟡 WARN (action item):** BILATERAL_ANCHOR_COVERAGE_PCT < 70% OU ≥2 B-IDs faltando individualmente mesmo que global ≥70 → listar B-IDs faltantes + arquivo(s) teste esperado(s) por keyword mapping.
   - **🟢 FULLY LINKED:** ≥70% E B-IDs individuais missing <2 → green. Bônus score §7.1 se ≥90%.

**3.5.2 Bilateral 2/3 — SPEC §4.4 Mermaid B-ID refs set vs §4.2 real Behavior Table set (diagramas não mentem)**

> Erro comum em specs longas: diagrama ganhou B-11 mas tabela só tem até B-10 (orphan) OU tabela tem B-3/B-4 mas nenhum diagrama referencia mesmo com mermaid_required=true.

Procedimento:
1. Construir sets:
   - `MERMAID_REF_SET = SBE_MERMAID_BIDS ∩ B` (só B-, ignora AB- para este check)
   - `TABLE_B_SET = { SBE_BEHAVIORS[].b_id }`
2. **Diff bidirecional:**
   - **Orphan refs (diagrama tem, tabela NÃO tem):** `MERMAID_REF_SET \ TABLE_B_SET` → WARN se non-empty. Ex: "B-11, B-12 aparecem no sequenceDiagram mas NÃO existem na §4.2 Behavior Table — remover do diagrama ou adicionar rows na tabela."
   - **Missing diagram refs (tabela tem ≥2, NENHUM diagrama referencia):** (TABLE_B_SET \ MERMAID_REF_SET) ≥ 2 ENTRIES E `mermaid_required === true` (frontmatter) → WARN. Ex: "mermaid_required=true mas B-2, B-5, B-7 da tabela NÃO aparecem em nenhum dos 3 diagrams §4.4 — rotular nós/edges com B-X para garantir bilateralidade."
3. AB-IDs anti-behavior no diagrama é OPTIONAL por padrão; se frontmatter `ab_count ≥ 3` E `erd_required=true` → WARN soft se 0 AB- no ERD (sem bloqueio).

**3.5.3 Bilateral 3/3 — SPEC §4.4.3 ERDiagram ↔ Migration SQL + TypeORM @Entity real**

> **Hard gate só aplica SE:** `erd_required === true` (frontmatter §0.4) E diff tem arquivos migration (`**/migrations/*.sql`, `**/migrations/*.ts`) OU entity (`*.entity.ts`, `@Entity()`) NOVOS/MODIFICADOS. Caso contrário → ⚪ N/A marcado no resumo.

Procedimento de cruzamento:
1. **Entidade declarada ERD existe no código?** cada entity name no erDiagram → grep `@Entity.*<name>` no diff. Missing → WARN "Entidade `<X>` declarada no ERD mas @Entity TypeORM NÃO encontrada no diff."
2. **Cardinalidade FK + ON DELETE rule match?** cada FK no ERD (cardinalidade Mermaid `}|`/`o|` etc) → cruzamos com migration SQL `REFERENCES <target>(id) ON DELETE <CASCADE|SET NULL|RESTRICT|NO ACTION>` e com TypeORM `@ManyToOne({ onDelete: "CASCADE" })`. Mismatch cardinalidade ou onDelete → WARN "Cardinalidade ERD `Order }|--|{ OrderItem` difere de migration `ON DELETE RESTRICT` (esperado CASCADE pela cardinalidade 1:N forte)."
3. **Campos constraints ≥3 declarados ERD realmente existem?** se ERD lista campos com `UK`/`CHECK`/`UNIQUE` explicitamente → grep `ADD CONSTRAINT <nome> UNIQUE` ou `UNIQUE(col, col2)` ou `@Index({ unique: true })` no diff. ≥1 constraint declarada no ERD mas ausente schema → WARN "UK `uk_order_stripe_pi_unique` existe no ERD mas migration não tem ADD CONSTRAINT nem @Index unique."
4. **Severidade:** Todos findings ERD = **🟡 WARN NÃO bloqueante** por default (muitas vezes ERD é "target state" e migration incremental). Se ≥3 mismatches + risco alto (FK ON DELETE errado em tabela de payments/tickets) → marcar como upgrade: **🔴 BLOCK se 1 dos mismatches é FK cardinalidade de integridade referencial forte (ex: Order 1:N Ticket mas ON DELETE CASCADE em Ticket deletaria tickets ao apagar Order — violação GDPR).**

---

#### §3.5 Report format — SbE Bilateral Extension (novo, REGRA7.9)

| Anchor ID | Regra comportamental | Verdict | Evidence + Action item se 🟡/🔴 |
|---|---|---|---|
| SBE-B1 | `bilateral_anchor_coverage_para_spec_Behaviors_test_files` | 🟢 FULLY LINKED | 9/10 B-IDs tem `// @ac B-X` 1ª linha dentro it() block. Coverage=90%. Files: [refundFlow.api.test.ts](file:///...) + [RefundService.unit.test.ts](file:///...). **Bônus +0.5 SCOPE_score §7.1 aplicado.** |
| SBE-B2 | `bilateral_mermaid_bid_refs_comportamento_tabela_real` | 🟡 WARN ORPHAN | Orphan refs: `B-11` existe no sequenceDiagram §4.4.1 mas NÃO tem correspondente na Behavior Table. Adicionar B-11 na tabela OU remover do diagrama. Missing refs count = 0 (ok, mermaid_required=true). |
| SBE-B3 | `bilateral_erd_cardinalities_constraints_migration_e_typeorm` | 🟡 WARN MISMATCH | ERD `OrderItem → Order }|--|{` (ON DELETE CASCADE esperado). Migration `20260415_refund.sql#L80` usa `ON DELETE RESTRICT`. Ajustar migration para CASCADE (order sem items = deletado sem risco orphans). UK declarado ERD `uk_refund_payment_id` → encontrado no @Index unique ✅. |
| SBE-B2-alt | `(exemplo 0% — hard block)` | 🔴 BLOCK ZERO ANCHORS | 0/7 B-IDs tem anchor bilateral. NENHUM arquivo teste modificado neste diff contém `// @ac B-X` pattern. Resolver: adicionar anchors OU EXPLICIT_OVERRIDE_BILATERAL_SKIP justificado + decision.log entry. |

---

## 4. CHECK 3 — 📘 Documentação ATUALIZADA (AGENTS / README / runbooks / CLAUDE)

### 4.0 Pre-check OBRIGATÓRIO (ANTES de usar heurísticas) — Relevância + Docstrings

Esta etapa NÃO é opcional. Rode em TODO diff, mesmo pequeno.

| Item Obrigatório | Pergunta a responder (verificação) | Verdict | Evidence |
|---|---|---|---|
| **Relevance Check 1** (engineering-contracts §22.1) | "Esta mudança altera contrato público, comandos, UX/UI, onboarding, premissas arquiteturais, fluxos deploy/runbook, ou APIs públicas?" Se SIM → docs obrigatórios. Se NÃO → justificar 1 linha se diff >5 arquivos ou >150 linhas. | 🟢 Respondido | Linha justificativa em decisions.log OU marcado SIM/NÃO em report |
| **Relevance Check 2** (engineering-contracts §22.1) | "Um humano ou agente lendo este código daqui a 3 meses se beneficia de uma explicação?" Se TALVEZ ou SIM → docs obrigatórios. | 🟢 Respondido | Decisão registrada no report |
| **Docstrings Públicos** (engineering-contracts §22.2) | Diff adicionou ou alterou funções/métodos/classes públicas, módulos, tipos customizados difíceis? Cada item novo tem docstring/JSDoc/TSDoc com PROPÓSITO + observações intrincadas (NÃO inputs/outputs se há tipagem)? Funções privadas intrincadas também devem ter. | 🟢 FULL / 🟡 PARCIAL / 🔴 ZERO | Lista arquivos/fns faltando docstring |

> **HARD FAIL:** Se os 3 itens acima NÃO forem verificados explicitamente, CHECK 3 não pode ser marcado 🟢 de forma alguma.

### 4.1 Heurísticas de trigger (QUANDO documentar — depois do pre-check 4.0)

| Mudança no diff | Documento OBRIGATÓRIO atualizar |
|---|---|
| Novo `/commands/che-*.md` ou `skills/*/SKILL.md` | **README.md §5 tabela comandos** (contagem + linha nova) + top banner contagem. Opcional: §6 cheatsheet se é comando diário. |
| Nova premissa arquitetura, novo hook, novo contrato | **AGENTS.md** da app ou repo-level, **CHE_RULES.md** se for cross-cutting, **CLAUDE.md** |
| Nova variável de ambiente (ver também CHECK 4) | `.env.example` + README seção "env vars required" + app-level config doc |
| Novo endpoint público / API route pública / breaking change | **README do package**, docs/api/, **OpenAPI/Swagger** se existir |
| Runbook alterado, comando deploy alterado, CI passo novo | **`.github/workflows/*.yml` comentários**, `docs/runbook-*.md` se existir |
| Refatoração arquitetura importante | **AGENTS.md** app-level + decision log `docs/decisions.md` se existir |

### 4.2 Passo 4.2 — Cruzar diff .md/.yml contra triggers

Do patch cumulativo:
1. Listar todos `.md`, `.yml`, `.yaml`, `.json schema`, `.toml config` alterados
2. Para CADA trigger que aplicar, marcar:
   - 🟢 DOCUMENTADO se arquivo correspondente apareceu no diff e conteúdo alterado combina com trigger keyword
   - 🟡 PARCIAL se documentou um lugar só mas faltou outro (ex: nova skill foi README §5 mas faltou contagem banner no topo)
   - 🔴 NÃO DOCUMENTADO se trigger aplicou e nenhum doc foi tocado

### Passo 4.3 — Report format, nomes REGRA7.9

| Trigger / Item | Regra comportamental | Verdict | Evidence doc path |
|---|---|---|---|
| Novo comando `/che-scope-check` adicionado | `atualizacao_documental_para_comando_che_scope_check_no_readme_e_contagem` | 🟢 DOCUMENTADO | [README.md#L244-L267](file:///...) §5 tabela linha 18 + banner topo contagem 17→18 atualizada |
| Nova env var `STRIPE_CONNECT_SECRET` (CHECK 4) | `atualizacao_documental_para_env_var_stripe_connect_secret_no_dotenv_example_e_parser` | 🟡 PARCIAL | `.env.example` tem a var mas `packages/config/src/env.ts` zod schema NÃO validou tipo (string required) |
| Nova arquitetura offline scanner | `atualizacao_documental_para_arquitetura_offline_no_agents_md_e_claude_md` | 🔴 NÃO DOCUMENTADO | Diff altera 12 arquivos scanner offline. `packages/scanner/AGENTS.md` + `CLAUDE.md` SEM alterações. Adicionar §scanner offline architecture. |

---

## 5. CHECK 4 — 🔐 Novas variáveis de ambiente = DECLARADAS no INFRA/ENV parser

### 5.1 Detectar usage NOVO de env var no diff

Regex patterns (todos languages, case-insensitive match whole words):
```
process\.env\.[A-Z0-9_]+
Deno\.env\.get\(["']([A-Z0-9_]+)
os\.environ\[["']([A-Z0-9_]+)
os\.getenv\(["']?([A-Z0-9_]+)
ENV\["?([A-Z0-9_]+)"?\]
env\(["']([A-Z0-9_]+)
z\.object\(\{\s*([A-Z0-9_]+)
```

Produz `ENV_USAGE[] = {var: string, file: path, line: n, lang: ts|py|rs|go|sh}`.

### 5.2 Cruzar com DECLARATIONS

Procurar em **TODO O REPO (não só diff)** declarations de cada ENV_USAGE[i]:

| Declaration type | Onde procurar |
|---|---|
| Zod schema env parser | `packages/config/src/env.ts`, `env.ts`, `config/env.ts`, `src/env/index.ts`, `app/env.ts`, next.config env |
| `.env.example`, `.env.local.sample`, `.env.dist` | repo root, apps/*, packages/* |
| Vercel (se projeto usa) | `vercel.json` env keys, OR Railway/Railway.tf |
| Terraform / AWS env | `*.tf` environment blocks, SSM parameter store names |
| Docker / K8s | `Dockerfile ENV`, k8s `ConfigMap`, `helm values.yaml` |
| CI GitHub Actions | `.github/workflows/*.yml` env blocks se for var de CI only |

Cada env var NOVAS vs diff marcada:
- 🟢 DECLARADA: aparece em ≥1 declaration **E** (se zod schema) tem tipo validado (z.string().min(1), z.number(), etc.)
- 🟡 DECLARADA FRAQUEZA: aparece em .env.example MAS NÃO no zod schema parser (sem runtime validation). Ou zod optional sem default.
- 🔴 NÃO DECLARADA: Nenhuma declaration encontrada no repo. Apontar: qual var, qual tipo esperado, onde adicionar (packages/config/src/env.ts + .env.example ambos)

### Passo 5.3 — Report format REGRA7.9

| Variável | Regra comportamental | Verdict | Onde declarar (se 🔴/🟡) |
|---|---|---|---|
| `ANALYTICS_S3_BUCKET` | `declaracao_env_var_no_parser_para_analytics_s3_bucket` | 🟢 DECLARADA | `packages/config/src/env.ts` z.string() + `.env.example` linha 42 |
| `STRIPE_CONNECT_SECRET` | `declaracao_env_var_no_parser_para_stripe_connect_secret` | 🟡 FALTA VALIDAÇÃO RUNTIME | `.env.example` linha 37 OK. **Falta** `packages/config/src/env.ts` zod entry + default throw se ausente em prod |
| `ETL_SENTRY_DSN` | `declaracao_env_var_no_parser_para_etl_sentry_dsn` | 🔴 NÃO DECLARADA | Usada em `etl/ingest.ts#L18` sem declaration. Adicionar em packages/config env schema zod.string().url() + .env.example. |

---

## 6. CHECK 5 — 🧩 LEAN / KISS / YAGNI — Overengineering Scanner (12 categorias genéricas L1-L12 + 13 Ousterhout RED FLAGS Appendix D)

> **Pilar novo introduzido 2026-09.** Combate LLM overengineering by default. Cada linha de código nova tem que justificar sua existência contra o scope explícito do diff. NÃO é "clean code gosto pessoal"; é YAGNI + blast-radius reduction + reuse-before-create do engineering-contracts §1 §4.
>
> **Integração Ousterhout (APoSD Appendix D canônico):** Depois de rodar as 12 categorias L1-L12, aplique também as 13 RED FLAGS Appendix D (D.1). Mesmo formato finding com mesmo downgrade scope justificador AC. Severidade default no scope-checker: HIGH (RF01-RF04), MEDIUM (RF05-RF13). Cross-reference com findings do che-code-review no ship gate.

### 6.0 Pre-step — Justificador de escopo automático (downgrade severity quando a abstração é pedida no escopo)

Antes de aplicar as 12 categorias, construa:
- `SET_AC_SCOPED_KEYWORDS`: todas keyword comportamentais das ACs do CHECK 1 que mencionam "extensibilidade / múltiplos backends / strategy / abstrair X / trocar Y por Z no futuro" / items que EXPLICITAMENTE pedem flexibilidade.
- Para cada finding L1-L12:
  - SE finding matcha QUALQUER keyword em SET_AC_SCOPED_KEYWORDS → **DOWNGRADE 1 nível de severity AUTOMATICAMENTE** (HIGH→MEDIUM, MEDIUM→LOW, LOW→INFO allowlisted no report). A abstração foi requisitada no escopo; não é overengineering.
  - SE NÃO matchar nenhuma keyword → severity original.

### 6.1 Procedimento por categoria — 12 checks obrigatórios

Para CADA categoria abaixo, aplique os passos sobre o diff cumulativo (arquivos NOVOS + MODIFICADOS, NÃO o repo inteiro).

| ID | Trigger (regex / heurística) | Severidade default | Procedimento de detecção |
|---|---|---|---|
| L1 | Premature abstraction: Interface / abstract class com 1 implementação só | MEDIUM (HIGH se > 5 indireções totais no mesmo fluxo) | 1. Liste todas interfaces novas/modificadas: `interface\s+\w+` / `abstract class\s+\w+`. 2. Para cada, grep implementações: `implements\s+<NomeInterface>` / `extends\s+<NomeAbstract>`. 3. SE contagem implementações = 1 E NÃO é uma interface já existente no repo histórico → flag L1. 4. Grave: caminho indireções no call chain; se > 5 hops totais de interface/abstract → severity upgrade HIGH. |
| L2 | Strategy / Factory / Dispatcher pattern com 1 entrada só no switch/map | MEDIUM | 1. Ache `switch/case`, `Record<Enum, Handler>`, `Map<string, () => R>` NOVOS. 2. Conte entradas efetivas (cases não-default / keys não vazias). 3. SE count = 1 E NÃO há TODO/FIXME anexando "em seguida adicionamos segunda estratégia" → flag L2. |
| L3 | Wrapper/builder em volta de lib com 1 método e zero lógica extra | LOW (MEDIUM se > 3 arquivos de wrapper no mesmo diff) | 1. Ache classes/funcs NOVAS que só chamam lib deps direto: corpo do método = só `return lib.f(args)` sem validação/sem cache/sem retry/sem error mapping. 2. Nome contém "Factory", "Wrapper", "Client", "Provider" mas sem implementação extra. 3. SE ≥ 3 desses no mesmo diff → upgrade MEDIUM. |
| L4 | Factory createX() com body = 1 linha return new ConcreteX() sem nenhum if/switch | LOW | 1. Grep `function\s+create\w+\s*\([^)]*\)\s*\{` / `static\s+create\w+\s*\(`. 2. Body AST/sintaxe = `return new <ClasseConcreta>(mesmos params sem alteração)`. 3. Zero condicionais, zero fallback, zero cache. → flag L4. |
| L5 | Helper/utility com 1 ÚNICO uso no codebase inteiro | LOW (MEDIUM se > 20 linhas de helper) | 1. Para cada função/const EXPORTADA nova em `utils.*`, `helpers.*`, `*util*`: grep o nome. 2. Contagem de ocorrências = 2 (declaração + 1 uso) OU 1 se export default. 3. SE body > 20 linhas → upgrade MEDIUM. |
| L6 | Env VAR declarada em .env.example MAS NUNCA lida no código com process.env etc | HIGH se credencial/secret; MEDIUM se feature flag/toggle | 1. Liste vars novas em .env.example no diff. 2. Para cada VAR: grep `process.env.<VAR>` / Deno.env.get / os.environ / ENV[var] em TODO O REPO (não só diff, pois pode ser usada em arquivo não-alterado). 3. ZERO matches → flag L6. Credenciais = nome contém (KEY/SECRET/TOKEN/DSN/PASSWORD/AUTH) → HIGH; resto MEDIUM. |
| L7 | React useHook/custom component ≤ 2 linhas, chamado 1 vez | LOW | 1. React hooks NOVOS: `function use\w+` → linhas body ≤ 2. 2. Component NOVO: `export default function \w+` com JSX ≤ 2 linhas e sem children/sem props além de hardcode. 3. Grep nome encontra exatamente 1 call site (fora do declaration file). → flag L7. |
| L8 | Genérico `<T>` / Type parameter usado 1 tipo concreto só em todos call sites | LOW | 1. Ache `function\s+\w+\s*<T[^>]*>` / `class\s+\w+\s*<T[^>]*>` NOVOS. 2. Grep todos call sites no diff + todo repo. 3. Todos passam MESMO tipo (ex: todos `invoke<Refund>` sem nenhuma outra variação). → flag L8. |
| L9 | Chain ≥ 3 hops de indireção sem valor real (X → Y → Z → operação db/rede real) | MEDIUM (HIGH se 1 dos hops tem lock tx held over network — cross-ref Category 0.3 do che-code-review) | 1. Para cada entrypoint público (router handler / tRPC procedure / controller): trace call chain até side effect real (DB read/write / HTTP / FS). 2. ≥ 3 funções/class.methods no meio que APENAS repassam args (zero validação/zero transform/zero branching). 3. Se alguma etapa tem queryRunner START TRANSACTION FOR UPDATE ainda não dado release e hop faz await fetch/stripe → upgrade HIGH (mesmo finding C0.3 code-review; linked). → flag L9. |
| L10 | Dead code comment-out / `// TODO` sem #ticket número / `FIXME` sem referência | MEDIUM se TODO/FIXME sem ticket; LOW dead code comentado | 1. Regex `/\/\/\s*TODO\b(?!\s*[:(]?\s*[A-Z]{2,}-?\d+)/` (TODO sem ticket). 2. Regex `\/\*[\s\S]*?\*\/` blocos comentados com código sintaticamente válido (não docstring). 3. Blocos comentados + TODO sem id → flag L10. |
| L11 | Parâmetro de função que TODOS os call sites do diff passam o MESMO valor hardcoded | MEDIUM | 1. Para cada função nova/modificada exportada: lista params. 2. Para cada param não-trivial que não é last: grep todos call sites no diff. 3. 100% dos calls passam literal exato mesmo valor (ex: todos `fn(..., "gbp")`). 4. Nenhum call site usa outro valor. → flag L11. |
| L12 | Lookup table / Record / Config table com 1 ENTRY só | LOW (exceto se 1 entry + >30 linhas de bloco inteiro → MEDIUM) | 1. Regex `=\s*\{\s*\w+\s*:\s*` + fecha chaves em < 5 linhas DEPOIS → só 1 key. 2. `Record<K,V>` + initialization só 1 key. 3. Nenhuma outra key adicionada em outros arquivos do diff. → flag L12. |

### 6.2 Report format CHECK 5 — tabela 4 colunas REGRA7.9

| ID | Regra comportamental (verbo_objeto_para_alvo) | Severidade (após downgrade scope) | Evidence (path:lines) + Justificador de escopo se aplicou |
|---|---|---|---|
| L1 | `overengineering_interface_com_1_implementacao_so_refund_repository` | MEDIUM | [RefundRepository.ts#L5-L30](file://...) IRefundRepository. Nenhuma AC pede múltiplos backends. |
| L6 | `env_var_declarada_sem_uso_refund_timeout_ms` | MEDIUM | [.env.example#L41](file://...) REFUND_TIMEOUT_MS=3000. ZERO ocorrências process.env.REFUND_TIMEOUT_MS no código. |
| L11 | `parametro_mesmo_valor_todas_calls_currency_refund` | INFO allowlisted | [refundService.ts#L18](file://...) issueRefund(currency). AC-1 do escopo disse "moeda GBP única por enquanto". Downgrade applied LOW→INFO. |

---

## 7. CHECK 6 — 🧮 SCORE FINAL 0-10 (média geométrica Scope × Lean)

> **Gate de bloqueio canônico usado pelo che-ship §0.9.1. Combina entrega e lean quality em um número comparável.**

### 7.1 Cálculo SCOPE sub-score (0-10)

Use CHECK 1 table verdicts:
```
TOTAL_ACs          = (DELIVERED+PARCIAL+MISSING)   (NÃO conta OOS)
DELIVERED_weighted = count(🟢 DELIVERED)
PARCIAL_weighted   = count(🟡 PARCIAL) × 0.5
SCOPE_score = 10 × (DELIVERED_weighted + PARCIAL_weighted) / max(1, TOTAL_ACs)
```

**⚡ SbE Bilateral Anchor Coverage adjustment (ONDA2 — só aplica se SBE_EXTENSION_ENABLED=true):**
```
# §3.5.1 coverage (já calculado)
BILATERAL_ANCHOR_COVERAGE_PCT = (B_COVERED_BY_ANCHOR ÷ max(1, B_COUNT_SPEC)) × 100
if (BILATERAL_ANCHOR_COVERAGE_PCT >= 90):
    SCOPE_score = clamp(SCOPE_score + 0.5, 0, 10)   # BÔNUS bilateral forte
elif (BILATERAL_ANCHOR_COVERAGE_PCT < 70 AND BILATERAL_ANCHOR_COVERAGE_PCT > 0):
    SCOPE_score = clamp(SCOPE_score - 1.0, 0, 10)   # PENALIDADE coverage fraco
# 0% anchors = BLOCK independente do score (veredito §8.1 tem check 🔴 item)
```

Exemplo: 8🟢 + 1🟡 + 1🔴 → SCOPE base = 10 × (8 + 0.5)/10 = **8.5**
Com bilateral anchor coverage 92% (SbE ON) → SCOPE ajustado = clamp(8.5 + 0.5, 0, 10) = **9.0**

### 7.2 Cálculo LEAN sub-score (0-10)

Use CHECK 5 findings severities:
```
LEAN_penalty =
    (count(🔴 HIGH_check5) × 2)
  + (count(🟡 MEDIUM_check5) × 1)
  + (count(🔵 LOW_check5) × 0.3)
LEAN_score = clamp(10 − LEAN_penalty ÷ 2, 0, 10)
```
Exemplo: 1 HIGH + 5 MEDIUM + 7 LOW → penalty = 2 + 5 + 2.1 = 9.1 ÷ 2 = 4.55 → LEAN = 10 − 4.55 = **5.45**

### 7.3 FINAL Score (média geométrica — exige AMBOS bons)

```
FINAL_score = sqrt(SCOPE_score × LEAN_score)
```
Exemplo: sqrt(8.5 × 5.45) = sqrt(46.3) = **6.80**

### 7.4 Regra CLASSIFICAÇÃO FINAL usada no gate

| Limiar FINAL_score | Nível | Ação no che-ship §0.9 |
|---|---|---|
| **≥ 9.0** | Excellent | Green + auto-proceed |
| **≥ 7.0** | Acceptable | Green + auto-proceed (THRESHOLD DEFAULT) |
| **5.0 – 6.9** | Atention | 🟡 CONDICOES → mostra action items L-M → pergunta user prossegue? |
| **< 5.0** | Poor | 🔴 BLOCK SHIP → corrige antes |

Além do score numérico, **SE houver QUALQUER 🔴 item em QUALQUER um dos 4 checks legados (1-4), o verdict final automaticamente cai para 🔴 BLOQUEADO**, independente do score. É a regra §6.1 antiga, preservada.

---

## 8. 🎯 Verdict final + relatório agregado (ATUALIZADO 2026-09 p/ 6 checks)

### 8.1 Regra de cálculo

```
Verdict =
  🔴 BLOCKED  se (ANY check tem ≥1 item 🔴)  OU  (FINAL_score < 5.0)
  🟡 CONDICOES se (NO check tem 🔴)  e  (ANY item tem 🟡)  OU  (5.0 ≤ FINAL_score < 7.0)
  🟢 APPROVED se (FINAL_score ≥ 7.0) AND (ALL items são 🟢/⚪/INFO) E (ZERO itens 🔴)
```

### 8.1 🔴 STORAGE PREFLIGHT OBRIGATÓRIO (ANTES DE ESCREVER O RELATÓRIO)

> MORATÓRIA engineering-contracts §20: Nenhum asset na worktree. Tudo em che-sessions via helper único.

Rode EXATAMENTE este bloco ANTES de construir qualquer path:
```bash
CHE_HOME="${CHE_HOME:-$HOME/.trae}"
CONTRACT="$CHE_HOME/contracts/che_sessions_contract.sh"
[ -f "$CONTRACT" ] && source "$CONTRACT" || { echo "❌ Contract $CONTRACT missing — exit 98"; exit 98; }
SESSION_ID="${CHE_CURRENT_SESSION_ID:-fallback-scope-session}"
if [ -n "${WORKTREE_ROOT:-}" ] && [ -d "$WORKTREE_ROOT" ]; then
  che_compute_paths "$WORKTREE_ROOT" "$SESSION_ID" "$PWD"
  che_ensure_session_dirs "$WORKTREE_ROOT"
fi
```

### 8.2 Output header + relatório salvo em

**Construir path com o helper — NUNCA manual:**
```bash
# SCOPE = workspace-shared (durável, reusável em futuras sessões desta worktree)
# related_id = slug da review (ex: pr-382 ou feat-FLO-714 ou task-T1)
SCOPE_CHECK_PATH="$(che_output_path "scope_check" "scope-check" "<related_id>" "workspace" "md")"
```
Resultado exemplo: `$CHE_WORKSPACE_SHARED/scope_check/pr-382/20260902-140000-scope-check.md`
→ Timestamp UTC no prefix = ordenação automática; related_id agrupa todas scope-checks da mesma entidade.

Primeira página do relatório (sempre no TOPO):

```markdown
# 🔍 Scope Check — <slug>

## 0. Meta
- **Scope source:** (PRD path / ticket URL / task-graph / scope free-text / PR body) — pick all que foram usados
- **Mode:** A=GitHub PR #<id> (url) | B=Worktree local <path> vs base <branch>
- **Diff:** N files changed / +X additions / -Y deletions
- **Final Score 0-10:** `<FINAL>` (SCOPE: `<SCOPE>` · LEAN: `<LEAN>`)

## 1. Verdict RESUMO 6+1 checks (SbE extension adicionada ONDA2)

| # | Check | 🟢 | 🟡 | 🔴 | ⚪ |
|---|---|---|---|---|---|
| 1 | 🔍 Entrega escopo completo | 8 | 1 | 1 | 2 OOS |
| 2 | 🧪 Cobertura testes unit/e2e | 6 | 2 | 1 | 0 |
| 2-ext | ⚡ SbE Bilateral (anchors + diagrams + ERD) | 2 rows ok | 1 ERD mismatch | 0 | 1 N/A erd_required=false |
| 3 | 📘 Docs atualizadas | 3 | 1 | 0 | 5 N/A |
| 4 | 🔐 Novas env vars declaradas | 1 | 1 | 1 | 0 |
| 5 | 🧩 Lean/YAGNI Overengineering | — | 5 L (MED) | 1 H (L6) | 7 allowlisted |
| 6 | 🧮 Score Final 0-10 | **6.80** | 7.0 threshold | — | — |

**👉 Verdict Final:** 🔴 BLOCKED / 🟡 CONDICOES / 🟢 APPROVED

## 2. Action items (ordenados 🔴 primeiro)
1. 🔴 [Check1, AC-3] Entregar qrcode offline scanner em scanner/lib/scan.ts (#L40-L120 expected)
2. 🔴 [Check2, AC-3] Criar scanner.spec.ts caso offline cache fallback
3. 🔴 [Check4] Declarar ETL_SENTRY_DSN em packages/config zod + .env.example
4. 🔴 [Check5 L6] Remover env REFUND_TIMEOUT_MS do .env.example ou adicionar uso real no código
5. 🟡 [Check1, AC-2] Acrescentar destination stripe connect API call em refund.ts
6. 🟡 [Check3] Validar runtime zod STRIPE_CONNECT_SECRET em env parser
...

↓ Detalhes cada check em §2..§7 (tabelas 4 colunas, nomes REGRA7.9)
```

No final do relatório: **como corrigir rápido** para próximo audit passar (1-2 comandos ou 1-2 arquivos).

---

## 7. NOMEAÇÃO REGRA7.9 (enforced em TODO o relatório)

NÃO é permitido em LUGAR NENHUM do relatório:
- ❌ `qualidade_boa`, `funciona`, `implementado_bem`, `cobertura_suficiente`
- ❌ `AC-FLO-732-entregue`, `§4.2 revisado`, `FLO-513 passing`
- ✅ **OBRIGATÓRIO:** `<verbo_objeto>_para_<alvo_comportamental>` em TODAS as regras das tabelas dos 4 checks.

Ex:
```
entrega_de_escopo_completo_para_<slug_ac>
cobertura_de_teste_unitario_ou_e2e_para_<comportamento>
atualizacao_documental_para_<mudanca>_em_<doc>
declaracao_env_var_no_parser_para_<VAR_NAME>
```
