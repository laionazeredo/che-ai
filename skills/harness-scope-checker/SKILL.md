---
name: "harness-scope-checker"
description: "6-check scope audit persona (CANONICAL 2026-09: 4 checks legacy + 2 new). From PRD/ticket/task-graph + GitHub PR OR local worktree, validates: (1) every acceptance criteria / item DELIVERED in diff with file evidence, (2) unit/e2e tests exist matching behavioral names for expected behavior, (3) required documentation is updated (AGENTS, README, runbooks, CLAUDE), (4) any NEW env var has corresponding declaration in infra/env parser (zod schema, .env.example, terraform/railway/vercel vars), (5) LEAN/KISS/YAGNI — overengineering scanner 12 categorias L1-L12 + justificador de escopo, (6) SCORE FINAL 0-10 media geometrica scope x lean. Invoked by /harness-scope-check or as SHIP gate before PR draft (harness-ship §0.9 GATES order 1)."
---

# Harness — Scope Checker (6-check audit persona)

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

## 6. CHECK 5 — 🧩 LEAN / KISS / YAGNI — Overengineering Scanner (12 categorias genéricas L1-L12 + 13 Ousterhout RED FLAGS Appendix D)

> **Pilar novo introduzido 2026-09.** Combate LLM overengineering by default. Cada linha de código nova tem que justificar sua existência contra o scope explícito do diff. NÃO é "clean code gosto pessoal"; é YAGNI + blast-radius reduction + reuse-before-create do engineering-contracts §1 §4.
>
> **Integração Ousterhout (APoSD Appendix D canônico):** Depois de rodar as 12 categorias L1-L12, aplique também as 13 RED FLAGS Appendix D (D.1). Mesmo formato finding com mesmo downgrade scope justificador AC. Severidade default no scope-checker: HIGH (RF01-RF04), MEDIUM (RF05-RF13). Cross-reference com findings do harness-code-review no ship gate.

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
| L9 | Chain ≥ 3 hops de indireção sem valor real (X → Y → Z → operação db/rede real) | MEDIUM (HIGH se 1 dos hops tem lock tx held over network — cross-ref Category 0.3 do harness-code-review) | 1. Para cada entrypoint público (router handler / tRPC procedure / controller): trace call chain até side effect real (DB read/write / HTTP / FS). 2. ≥ 3 funções/class.methods no meio que APENAS repassam args (zero validação/zero transform/zero branching). 3. Se alguma etapa tem queryRunner START TRANSACTION FOR UPDATE ainda não dado release e hop faz await fetch/stripe → upgrade HIGH (mesmo finding C0.3 code-review; linked). → flag L9. |
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

> **Gate de bloqueio canônico usado pelo harness-ship §0.9.1. Combina entrega e lean quality em um número comparável.**

### 7.1 Cálculo SCOPE sub-score (0-10)

Use CHECK 1 table verdicts:
```
TOTAL_ACs          = (DELIVERED+PARCIAL+MISSING)   (NÃO conta OOS)
DELIVERED_weighted = count(🟢 DELIVERED)
PARCIAL_weighted   = count(🟡 PARCIAL) × 0.5
SCOPE_score = 10 × (DELIVERED_weighted + PARCIAL_weighted) / max(1, TOTAL_ACs)
```
Exemplo: 8🟢 + 1🟡 + 1🔴 → SCOPE = 10 × (8 + 0.5)/10 = **8.5**

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

| Limiar FINAL_score | Nível | Ação no harness-ship §0.9 |
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

### 8.2 Output header + relatório salvo em

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
- **Final Score 0-10:** `<FINAL>` (SCOPE: `<SCOPE>` · LEAN: `<LEAN>`)

## 1. Verdict RESUMO 6 checks

| # | Check | 🟢 | 🟡 | 🔴 | ⚪ |
|---|---|---|---|---|---|
| 1 | 🔍 Entrega escopo completo | 8 | 1 | 1 | 2 OOS |
| 2 | 🧪 Cobertura testes unit/e2e | 6 | 2 | 1 | 0 |
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
