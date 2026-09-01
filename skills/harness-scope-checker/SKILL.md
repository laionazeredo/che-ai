---
name: "harness-scope-checker"
description: "4-check scope audit persona. From PRD/ticket/task-graph + GitHub PR OR local worktree, validates: (1) every acceptance criteria / item DELIVERED in diff with file evidence, (2) unit/e2e tests exist matching behavioral names for expected behavior, (3) required documentation is updated (AGENTS, README, runbooks, CLAUDE), (4) any NEW env var has corresponding declaration in infra/env parser (zod schema, .env.example, terraform/railway/vercel vars). Invoked by /harness-scope-check or as SHIP gate before PR draft."
---

# Harness — Scope Checker (4-check audit persona)

> **SHARED REFERENCES (CANONICAL — NÃO DUPLICAR corpo aqui):**
> - GitHub CLI gh auth + PR diff fetch: `../harness-code-review/references/_shared_checklists/GITHUB_CLI_COMMON.md`
> - Stack auto-detection (test runners, doc files, env parsers): `../harness-qa/references/_shared_checklists/NX_PNPM_COMMON.md`
> - Security/PII/RLS checklist: `../harness-code-review/references/_shared_checklists/SECURITY_PII_COMMON.md`

Auditor persona com **2 modos mutuamente exclusivos** (escolher EXATAMENTE 1). **Sempre retorna relatório estruturado com evidence por linha e nomes REGRA7.9 comportamento observável.**

---

## 0. Preconditions — 2 modos + binding check

### 0.1 WORKTREE SESSION BINDING CHECK (engineering-contracts §19, NÃO NEGOCIÁVEL)

Run ANTES de decidir o modo.

1. **Ler Level1 Global Index PRIMEIRO:** Read `harness_registry_path`. Find LAST `STATUS=BOUND` entry using the effective session id from `harness_current_session_id`. Use its `WORKTREE_ROOT` como sessão default.
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

Mesma tabela do harness-qa §1.4. Detecta Vitest, Jest, Playwright, Cypress, pytest, cargo test, go test etc.

### Passo 3.2 — Detectar arquivos de teste existentes NO DIFF

Do patch cumulativo, filtrar:
- Files matching: `*.test.*`, `*.spec.*`, `**/__tests__/**`, `**/e2e/**`, `**/playwright/**/*.spec.*`, `*_test.go`, `tests/**/*.py`
- + NÃO testes, mas SUT (system under test) arquivos correspondentes.

### Passo 3.3 — Mapear AC comportamental → describe()/it() behavioral names

REGRA7.9: Nomes de suites/testes DEVEM ser comportamento observável. Nomes ruins (FLO-123, test(), it1, shouldWork) não contam como evidence coverage.

Raciocínio por AC:
- Para cada AC comportamental tipo "usuário consegue aplicar refund stripe connect" → procurar nos testes strings como: `refund`, `stripe connect`, `connected account`, `refund succeeded`, `refund failed`
- Se descreve comportamento = 🟢 TESTED
- Se tem arquivo de teste pro módulo MAS nenhum caso acerta keyword da AC → 🟡 PARCIAL (quais testes existem vs falta qual comportamento específico)
- Se SUT foi alterado e ZERO arquivo de teste alterado pra área → 🔴 NOT TESTED (qual behavior, qual file test criar)

### Passo 3.4 — Report format

| Área / AC | Regra comportamental | Verdict | Evidence test (path:lines) |
|---|---|---|---|
| AC-1 refund | `cobertura_de_teste_unitario_ou_e2e_para_refund_connect_account` | 🟢 TESTED | [refund.test.ts#L102-L145](file:///...) it(`refunds_connected_account_destination_correctly`) |
| AC-2 qrcode offline | `cobertura_de_teste_unitario_ou_e2e_para_qrcode_offline_scan` | 🟡 PARCIAL | [scanner/scanner.test.ts#L5-L18](file:///…) suite existe, só happy path online. **Faltou** caso offline + cache fallback. |
| AC-3 login google | `cobertura_de_teste_unitario_ou_e2e_para_login_google_oauth_redirect` | 🔴 NOT TESTED | `packages/auth/src/google.ts` alterado, NENHUM `*.test.*` em `packages/auth/**` tocado. Criar `google-login.spec.ts` com casos: redirect_uri, state param, token exchange. |

---

## 4. CHECK 3 — 📘 Documentação ATUALIZADA (AGENTS / README / runbooks / CLAUDE)

### 4.1 Heurísticas de trigger (QUANDO documentar)

| Mudança no diff | Documento OBRIGATÓRIO atualizar |
|---|---|
| Novo `/commands/harness-*.md` ou `skills/*/SKILL.md` | **README.md §5 tabela comandos** (contagem + linha nova) + top banner contagem. Opcional: §6 cheatsheet se é comando diário. |
| Nova premissa arquitetura, novo hook, novo contrato | **AGENTS.md** da app ou repo-level, **HARNESS_RULES.md** se for cross-cutting, **CLAUDE.md** |
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
| Novo comando `/harness-scope-check` adicionado | `atualizacao_documental_para_comando_harness_scope_check_no_readme_e_contagem` | 🟢 DOCUMENTADO | [README.md#L244-L267](file:///...) §5 tabela linha 18 + banner topo contagem 17→18 atualizada |
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

## 6. 🎯 Verdict final + relatório agregado

### 6.1 Regra de cálculo

```
Verdict =
  🔴 BLOCKED  se ANY check tem ≥1 item 🔴              → action items ordered by severity
  🟡 CONDICOES se NO check tem 🔴, e ANY item tem 🟡    → list what needs fixing (lower bar)
  🟢 APPROVED se ALL items são 🟢 ou ⚪ (NENHUM 🔴/🟡)
```

### 6.2 Output header + relatório salvo em

```
$HARNESS_WORKSPACE_SHARED/scope-check_<slug>_<YYYYMMDD>.md
```

Primeira página do relatório (sempre no TOPO):

```markdown
# 🔍 Scope Check — <slug>

## 0. Meta
- **Scope source:** (PRD path / ticket URL / task-graph / scope free-text / PR body) — pick all que foram usados
- **Mode:** A=GitHub PR #<id> (url) | B=Worktree local <path> vs base <branch>
- **Diff:** N files changed / +X additions / -Y deletions

## 1. Verdict RESUMO 4 checks

| # | Check | 🟢 | 🟡 | 🔴 | ⚪ |
|---|---|---|---|---|---|
| 1 | 🔍 Entrega escopo completo | 8 | 1 | 1 | 2 OOS |
| 2 | 🧪 Cobertura testes unit/e2e | 6 | 2 | 1 | 0 |
| 3 | 📘 Docs atualizadas | 3 | 1 | 0 | 5 N/A |
| 4 | 🔐 Novas env vars declaradas | 1 | 1 | 1 | 0 |

**👉 Verdict Final:** 🔴 BLOCKED / 🟡 CONDICOES / 🟢 APPROVED

## 2. Action items (ordenados 🔴 primeiro)
1. 🔴 [Check1, AC-3] Entregar qrcode offline scanner em scanner/lib/scan.ts (#L40-L120 expected)
2. 🔴 [Check2, AC-3] Criar scanner.spec.ts caso offline cache fallback
3. 🔴 [Check4] Declarar ETL_SENTRY_DSN em packages/config zod + .env.example
4. 🟡 [Check1, AC-2] Acrescentar destination stripe connect API call em refund.ts
5. 🟡 [Check3] Validar runtime zod STRIPE_CONNECT_SECRET em env parser
...

↓ Detalhes cada check em §2..§5 (tabelas 4 colunas, nomes REGRA7.9)
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
