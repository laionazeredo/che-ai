# Harness Flockr — Global `.trae` — READ ME

> **Repo público:** `github.com/laionazeredo/trae-config`
> **Design philosophy:** KISS + YAGNI + blast radius mínimo (engineering-contracts §1).
> Documento único para entender TUDO o que o harness do Flockr implementa hoje.
> Se você é novo: leia **§0 INSTALL abaixo + §1 Visão geral + §2 Fluxo padrão Start → Dev → Ship**.
> Se você quer um comando: pule para **§4 Lista de comandos (17)** (§9 no final do arquivo).

---

## 0. 🚀 INSTALL — 3 comandos (fresh install · máquina NOVA)

Cenário: você abriu Trae em uma máquina NOVA, `~/.trae/` ainda não existe.

```bash
# 1. Clona repo público DIRETO em ~/.trae (RECOMENDADO: ~/.trae vira git repo)
gh repo clone laionazeredo/trae-config ~/.trae -- --depth 1

# 2. Instala deps TS (tsx executor zero-build + typescript strict + @types/node)
corepack enable
corepack pnpm --dir ~/.trae install --prefer-offline

# 3. Smoke rápido (OBRIGATÓRIO — 10s)
ls ~/.trae/commands | wc -l            # esperado = 17
corepack pnpm --dir ~/.trae decisions --help 2>&1 | head -3
```

Recarregue o Trae (ou feche/abra). Pronto. Como ~/.trae agora É um git repo (com upstream), atualizações futuras são um comando via §0.1 (fluxo CASO 1).

---

## 0.1 🔄 ATUALIZAR — pegar últimas versões do GitHub (SEM perder dados pessoais)

> **GARANTIA FUNDAMENTAL:** Nenhum dos 3 comandos abaixo **nunca** sobrescreve, renomeia ou deleta:
> `user_rules/*`, `bindings/registry.jsonl`, `memory/`, skills custom que VOCÊ adicionou em `skills/<sua-skill>/` que não existem no repo oficial.
> Ver §0.2 BLACKLIST abaixo para a lista completa.

### ⚡ MODO "SÓ QUERO A ÚLTIMA VERSÃO" — 1 comando, zero pensamento (RECOMENDADO para uso diário)

Você **não lembra** se instalou via git clone ou zip? **Não importa.** Este comando faz TUDO automaticamente:
1. Vai até o GitHub e baixa a ÚLTIMA versão oficial do `laionazeredo/trae-config` em `/tmp` (via `gh` se logado, via `git clone --depth 1 https://...` fallback público).
2. Detecta sozinho se seu `~/.trae` é um git repo (CASO 1) ou não (CASO 2).
3. Roda a estratégia correta de update para o seu caso.
4. Apaga a pasta temporária de fetch automaticamente (trap EXIT).

```bash
# DRY-RUN (padrão): baixa última versão, mostra relatório, NÃO ALTERA NADA no seu ~/.trae.
bash ~/.trae/scripts/self-update-harness.sh

# Se o relatório parece OK → APPLY de verdade:
bash ~/.trae/scripts/self-update-harness.sh --apply
```

Dependências mínimas (pelo menos 1, comuns em qualquer máquina dev):
- **Preferido:** `gh` (GitHub CLI) logado → `gh auth login`. Usa API autenticada (rate limits maiores).
- **Fallback:** `git` apenas → clone raso via HTTPS público, sem auth.

---

### 🟢 CAMINHO AVANÇADO 1 (target = clone git, controle granular)

Se você **sabe** que `~/.trae` foi clonado DIRETO do repo oficial (possui `.git/` com upstream `laionazeredo/trae-config`):

```bash
# Primeiro: dry-run. Nada altera. Mostra commits que vão entrar e avisos.
bash ~/.trae/scripts/update-harness.sh

# Se o relatório parece OK:
bash ~/.trae/scripts/update-harness.sh --apply
```

O que `update-harness.sh` faz para você NESTE caminho:
1. Detecta que `~/.trae` é git repo → usa CASO 1.
2. **Fail-closed contra alterações locais NÃO commitadas** em arquivos trackeados: se você modificou um `SKILL.md` oficial e não commitou, aborta com solução (commit ou stash).
3. Fetch remoto + lista commits pendentes (você vê exatamente o que vai entrar).
4. `git pull --ff-only` (NÃO cria merge automático; se divergência, aborta).
5. Se `package.json` / `pnpm-lock.yaml` mudaram → roda `pnpm install --prefer-offline` automaticamente.
6. `.gitignore` do repositório **automaticamente** protege `user_rules/`, `bindings/registry.jsonl`, `memory/` — esses arquivos **nunca são trackeados nem tocados pelo git pull**.

### 🟡 CAMINHO FALLBACK (se você NÃO quer ~/.trae como git repo)

Você baixou zip, copiou manualmente, ou por qualquer motivo `~/.trae/.git/` não existe. Update usa `install-harness.sh` em **modo --update não-destrutivo**:

```bash
# 1. Baixe a versão nova do repo oficial em uma pasta temporária
gh repo clone laionazeredo/trae-config /tmp/trae-src -- --depth 1

# 2. DRY-RUN (mostra novos arquivos e arquivos que serão atualizados com backup individual)
bash /tmp/trae-src/scripts/install-harness.sh --update

# 3. Aplica de verdade (sem --apply = nada muda)
bash /tmp/trae-src/scripts/install-harness.sh --update --apply
```

O que `install-harness.sh --update` faz NESTE caminho:
1. **NÃO renomeia nem deleta** `~/.trae` inteiro (comportamento antigo de fresh install).
2. Itera CADA subitem dentro de `commands/`, `skills/`, `contracts/`, etc:
   - Source tem, target não tem → cria novo (marcado `+ novo`).
   - Source tem, target tem e são diferentes → primeiro `mv target/x → target/x.bak-YYYYMMDD-HHMM` (backup individual NO MESMO diretório), depois copia novo por cima (marcado `~ updt`). Rollback manual é só `mv x.bak-* x`.
   - Source tem, target tem e idênticos → silent skip.
   - Source **NÃO** tem, target tem → **NUNCA TOCA**. Preserva 100% skills custom, comandos novos que você criou, arquivos extras pessoais.
3. Blacklist (user_rules, bindings/registry.jsonl, memory) → intocada, nem lida.
4. Roda pnpm install só se package.json / pnpm-lock.yaml realmente mudaram.

---

### Fresh install fallback (se quiser RESET TOTAL do harness, mas preservando seus dados)

Use **sem** a flag `--update`. Comportamento antigo: backup INTEIRO de `~/.trae` para `~/.trae.bak-YYYYMMDD-HHMM`, depois instala versão nova. Dados pessoais são copiados de volta automaticamente APENAS como estrutura vazia; para recuperar suas regras pessoais você copia manualmente da pasta `.bak-*`. Use só se quiser "zerar tudo" e recomeçar limpo.

```bash
gh repo clone laionazeredo/trae-config /tmp/trae-src -- --depth 1
bash /tmp/trae-src/scripts/install-harness.sh --dry-run
bash /tmp/trae-src/scripts/install-harness.sh --apply
```

### O que este repositório tem (capacidades)

| Camada | Conteúdo | Tamanho |
|---|---|---|
| **17 comandos** | `/harness-start`, `/harness-spec`, `/harness-ship`, `/harness-review`, `/harness-pr-comments`, `/harness-parallel`, `/harness-fig`, `/harness-decisions`… | 17 arquivos `.md` |
| **37 skills** | 17 personas time ágil simulado (SM / Dev / QA / Compliance / Ship) + 20 domínio (Stripe, Supabase Postgres, Next.js, tRPC, Terraform, Linear, Resend…) | 37 pastas |
| **3 hooks automáticos** | binding scissor (bloqueia path fora worktree), 3-layer dedup, lang-pt-check warn-only | 3 `.sh` |
| **CLI decisions TS** | 4 modos: summary / filter / tail / export csv\|tsv | `contracts/decisions-query.cli.ts` |
| **Contracts único** | path binding + 5 heurísticas token reduction + 4 helpers registry JSONL + 3 helpers decisions append | `contracts/harness_sessions_contract.sh` (17 helpers) |
| **Install + Update scripts** | `install-harness.sh` (fresh ou update não-destrutivo) + `update-harness.sh` (alias inteligente git vs zip) + `self-update-harness.sh` (⚡ 1-comando: baixa última versão do GitHub + auto-detecta caso) | 3 `.sh` |

### ⚠️ Blacklist — o que NÃO está versionado (dados LOCAIS por máquina)

Estes vivem na sua máquina e **nunca são commitados** (ver `.gitignore`):

```
memory/                  # sessões / perfil LLM (gerado pela IDE)
user_rules/*             # regras PESSOAIS (você que escreve: idioma, perfil, preferências)
bindings/registry.jsonl  # binding session_id → worktree root (REGRA 7.8; writer único contracts)
node_modules/  *.bak-*   # deps TS + backups install script
```

Regras de 3 camadas (precedência 1→3 HIGH): **user_rules (você)** > **contracts/** (aqui) > **skills/**. Não duplique regra em múltiplas camadas — o hook `posttooluse-3layer-dedup.sh` avisa quando isso acontece.

---

## 1. Estrutura do diretório `.trae/`

```
~/.trae/
├── README.md                          # ESTE ARQUIVO (ponto de entrada)
├── HARNESS_RULES.md                   # Corpo gate + processo (binding, scissor, paralelismo, SPEC gate)
├── HARNESS_COMMANDS.md                # Inventário comandos heavy (8) vs inline (5) + arquitetura 13 regras
├── REFERENCE_USER_RULES_MINIFIED.md   # Regras 1→8 + REGRA7.5 token reduction + 7.75 script mode + 7.8 registry JSONL
│
├── bindings/
│   └── registry.jsonl                 # Level 1 GLOBAL INDEX (AUTHORITY) append-only JSONL. NÃO Edit/Write manual.
│                                      # Único writer: contracts helper `harness_registry_append_jsonl`.
│
├── commands/                          # LEVES (5) inline markdown + HEAVY (8) = Skill wrapper + medianos (4). Total = 17 comandos.
│   harness-abort.md  harness-ci-fix.md    harness-decisions.md  harness-design.md
│   harness-diff.md   harness-figma.md     harness-fix.md        harness-manual-test.md
│   harness-parallel.md harness-pr-comments.md harness-review.md harness-ship.md
│   harness-skip.md   harness-spec.md      harness-start.md      harness-status.md
│   harness-summary.md
│
├── contracts/                         # SINGLE SOURCE OF TRUTH — tudo que é shell/writer/parser/reader mora AQUI.
│   harness_sessions_contract.sh           # path contract + 17 helpers (4 paths + 3 decisions + 5 token reduction + 4 registry + 1 dedup)
│   decisions-query.cli.ts                 # CLI decisions (TS strict, 0-build via tsx; 4 modos summary/filter/tail/export)
│
├── skills/                            # 34 skills = 17 HARNESS PERSONAS (workflow do time simulado) + 17 DOMÍNIO (infra/code).
│   —— 17 SKILLS DO HARNESS (time simulado) ——
│   engineering-contracts/                 # PRECEDÊNCIA MÁXIMA 1→18 regras + 3 apêndices
│   harness-scrum-master/                  # start gates 0.1→1.5 + task graph + task envelope
│   harness-developer/                     # TDD atomic DbC per task T1..TN
│   harness-executor-dispatcher/           # paralelismo Kahn waves + file locks
│   harness-qa/ harness-compliance/        # gates quality + security
│   harness-ship/                          # lint→CRÍTICO fix→doc→1 commit → DRAFT PR
│   harness-spec/                          # SPEC generator/validator 4 fontes input + approval loop
│   harness-code-review/ harness-pr-comments/ harness-ci-fixer/
│   harness-debugger-bugfix/ harness-manual-test-executor/
│   harness-diff-context/ harness-social-ui-designer/ harness-decisions-query/ (NOVO)
│   _shared_checklists/                    # SECURITY_PII_COMMON, GITHUB_CLI_COMMON, NX_PNPM_COMMON
│   —— 17 SKILLS DE DOMÍNIO (infra/code helpers) ——
│   adr-architecture, airtable, database-architect, database-schema-designer,
│   deno-expert, design-by-contract, devops-engineer, k8s-kind, linear,
│   mermaid-diagram-specialist, nestjs-best-practices, next-best-practices,
│   nx-workspace, pragmatic-programmer, rabbitmq-development,
│   remotion-video-production, test-driven-development, vercel-react-best-practices
│
├── hooks/                             # 3 hooks globais (auto, agent nem vê, enforcement automático)
│   pretooluse-worktree-binding.sh         # Hook1 §19: scissor check SESSION_ID → WORKTREE_ROOT
│   posttooluse-lang-pt-check.sh           # Hook3 §18: PT-BR text warn-only em writes
│   posttooluse-3layer-dedup.sh            # Hook2: dedup entre contracts ↔ user_rules ↔ skills
│
├── hooks.json                         # Config hooks (qual evento → qual script)
├── permission/global.json             # Permissões globais tool allow/deny
├── user_rules/                        # User rules injetadas por sessão (8 arquivos). CONTRATO: NÃO duplica regras.
└── memory/                            # (fora do .trae) ~/.trae/memory — histórico sessões/projects. NÃO editar manualmente.
```

---

## 1. Visão geral (o que o harness realmente FAZ)

É um **time ágil simulado inteiro em software**, 17 personas = 17 harness skills (+17 domínio), com gates obrigatórios para não entregar código quebrado.

```
          ┌─────────────────────── USER pede feature/bug ─────────────────────────┐
          │                                                                        ▼
┌───────────────────────┐  ┌─────────────────────┐  ┌────────────────────────────────┐
│  /harness-spec (LEVE) │  │ /harness-start      │  │ Developer TASK T1..TN serial   │
│  gera SPEC 15 campos  │─▶│ SM gates 0.1→1.5   │─▶│ + paralelismo executor-dispatcher│
│  + approval 1-pass A  │  │ + binding 2-level   │  │ + DbC pre/post conditions      │
└───────────────────────┘  └─────────────────────┘  └───────────────┬────────────────┘
                                                                     ▼
                                                    ┌────────────────────────────────┐
                                                    │ QA (build/lint/typecheck/tests) │
                                                    │ + compliance (PII/secrets/RLS) │
                                                    └───────────────┬────────────────┘
                                                                     ▼
                                                    ┌────────────────────────────────┐
                                                    │  /harness-ship (fim DE TUDO)    │
                                                    │  1 conventional commit + DRAFT  │
                                                    │  PR no GitHub (bottom-up stack) │
                                                    └────────────────────────────────┘
```

### 3 princípios NON-NEGOCIÁVEIS (§ contracts 1 + 2)
1. **KISS/YAGNI SEMPRE GANHA.** Nenhuma abstração a mais. Nenhuma nova dependência a menos.
2. **Single Writer Principle:** Qualquer dado compartilhado (decisions, registry, paths) tem **1 HELPER OFICIAL** só. Ninguém usa Edit/Write manual.
3. **Blast radius mínimo:** Nada de escrever em worktree sem binding. Nada de cross-worktree silencioso. Hook1 BLOQUEIA.

---

## 2. Fluxo padrão (Start → Dev → Ship) — 3 comandos

| Passo | Comando | O que faz (em alto nível) |
|---|---|---|
| 1 | **`/harness-spec input=desc`** (opcional) | Gera SPEC canônico 7 seções + YAML 15 chaves. Approval gate 1-pass A. Skip se SPEC já existe. |
| 2 | **`/harness-start --worktree <path>`** | Gates 7/7: 0.1 binding 2-level → 0.3 spec approval → 0.4 task graph + locks → 0.5 envelope → 1.0 QA empty → 1.2 compliance → 1.5 SM handoff to dev **(T1→ serial / ou paralelo Kahn)** |
| 3 | **`/harness-ship`** | Último gate: lint → CRITICAL/HIGH issues fix → sync docs AGENTS.md → 1 commit conventional (ex: `feat(api): add health endpoint FLO-123`) → push → **DRAFT PR** aberto → user assina review. |

**Comandos intermediários úteis:**
- `/harness-status` — snapshot gates 0→1, tasks done/running/pending, registry, binding.
- `/harness-abort` — mark CANCELLED, append decision, release locks (rollback limpo).
- `/harness-ci-fix <PR URL>` — diagnostics CI failing jobs + fix (1 task envelope).
- `/harness-fix expected=<X> reproduce=<steps>` — bugfix científico (hypothesize→instrument→reproduce→fix→verify).

---

## 3. Componentes centrais (detalhes importantes)

### 3a. Session Binding 2-LEVEL (§19 contracts) — resolve o chicken-and-egg

| Nível | Arquivo | O que guarda | Como escrever |
|---|---|---|---|
| **Level 1 GLOBAL (AUTHORITY)** | `~/.trae/bindings/registry.jsonl` append-only | **1 entry por sessão:** `session_id → worktree_root` + workspace_name, worktree_slug, branch, friendly_name, session_dir/workspace_shared paths, flags.LANG_PT_CHECK. | **ÚNICA MANEIRA:** `source contracts/harness_sessions_contract.sh && harness_registry_append_jsonl <sid> BOUND <wt> <json payload>` (dedup sha256 automático, python3 JSON safe). **NÃO Edit/Write manual.** |
| **Level 2 PER-SESSION (fora worktree)** | `$HARNESS_SESSION_DIR/binding.md` (caminho via contracts) | Mirror detalhado Level1 + re-binding chain history + audit chain handoff SM→Dev→QA→Ship. | Escreve SM no gate 0.1. |

**Hook 1 automático:** a CADA tool call Glob/Read/Grep/Edit/Write/RunCommand que toca paths, hook1 checa se path alvo começa com **WORKTREE_ROOT BOUND** OU **HARNESS_SESSIONS_ROOT (exception paths gerados)**. Se nenhum → **BLOCK exit code 2.** → agente tem que pedir re-bind explícito ou cancelar.

### 3b. Decisions Log (timeseries estruturado)

- **ÚNICA FONTE VERDADE:** `$HARNESS_WORKSPACE_SHARED/decisions.log.jsonl` (1 linha JSONL por entrada). **NÃO tem decisions.log.md. Removido 2026-08-30 para eliminar drifts/ambiguidade.**
- **ÚNICO writer:** helper `harness_append_decision_jsonl <wt_root> <event_type> <payload_json>` (idem registry: dedup + sort_keys + python3 safe).
- **4 modos query oficial** via skill `/harness-decisions` ou CLI TS `decisions-query.cli.ts` (exec via tsx):
  1. `summary --lang pt` (padrão): agrupa por event + spec_id, tabela humana PT-BR
  2. `filter --spec SPEC-X [--event APPROVAL] [--after YYYY-MM-DD] [--grep keyword]`
  3. `tail --last 20`
  4. `export csv|tsv --out /tmp/dec.csv`
- Shortcut: `corepack pnpm --dir ~/.trae decisions <JSONL_PATH> summary --lang pt`

### 3c. Token reduction caveman-style (5 heurísticas REGRA 7.5)

Regras que o agente aplica SEMPRE em outputs longos (env caps configuráveis, bypass global `HARNESS_FULL_OUTPUT=1`):

| H# | Helper shell | ENV default | Ação |
|---|---|---|---|
| H1 | `harness_tr_diff <diff>` | `HARNESS_TR_DIFF_MAX_LINES=500` | Remove headers `---/+++/@@` do git diff, só mantém `+/-` lines; cap 500 lines + footer aviso. |
| H2 | `harness_tr_read <total_lines> [max]` | `HARNESS_TR_READ_MAX_LINES=300` | Trim leitura >300 linhas; footer `"[...TRUNCADO lines X-Y / total T. Bypass: Read offset=N limit=M]"` |
| H3 | `harness_tr_collapse_blank` | `HARNESS_TR_COLLAPSE_BLANK=1` | ≥2 blank lines → 1; trailing whitespace strip. |
| H4 | `harness_tr_stdout` | `HARNESS_TR_STDOUT_MAX_CHARS=4000` | Cap stdout em 4000 chars + footer aviso. |
| H5 | `harness_tr_grep <pat> <path> [ext]` | `HARNESS_TR_GREP_CONTEXT=0` | lines-only compact (path:line:content), sem headers verbose grep; context default=0. |

### 3d. MVP Script Mode (REGRA 7.75 — DeepSeek-inspired, ZERO nova infra)

**Problema:** batch ≥3 tool calls (Read X → Grep Y → Edit Z) gasta N turnos LLM + N roundtrips chat-tool.  
**Solução leve (sem worker thread / sem .d.ts / sem run_code transport novo):**

```
SE (batch lógico ≥3 tool calls PURAMENTE LOCAIS) {
   ESCREVE 1 script bash/node CURTO (≤20 bash | ≤40 node) +
   EXECUTA tudo em 1 ÚNICO RunCommand
} else {
   1 tool call por vez (modo normal)
}
```
- **Quando usar:** Ler 3+ arquivos, grep pattern, substituir em massa, criar boilerplate, validações de sintaxe multi-arquivo.
- **Quando NÃO:** precisa de interação humana, browser, múltiplas worktrees cruzadas.
- **Regras script:** `set -euo pipefail` fail-fast, relatório curto ≤15 lines final, stdout aplica H4 se passar 4000 chars.
- **Exemplo real na REGRA 7.75:** task T1 route handler (Read route.ts + Grep fetch exports + Edit runtime=nodejs→edge) — ANTES 3 turnos / DEPOIS 1 turno RunCommand único.

### 3e. SPEC Approval Gate (corpo HARNESS_RULES §🟣)

- 4 fontes input: spec existente / ticket URL (Linear/ClickUp) / PRD Flockr-style .md / inline descrição breve
- 7 seções canônicas + YAML frontmatter 15 campos required
- **Gate Approval OBRIGATÓRIO ANTES start:** SEM SPEC Approved = NÃO passa gate 0.3 SM.
- Mecanismo override: SPEC-OVERRIDE com log obrigatório no decisions.

### 3f. Paralelismo (corpo executor-dispatcher Kahn algorithm)

- Task graph = TASK_ENVELOPES + file-lock conflict graph (2 Tn tocam mesmo arquivo = serial).
- Algoritmo Kahn topological sort → BATCHES independentes executam em paralelo (cap 4 default).
- Merge audit + scope/QA/compliance gates CADA batch, não só final.
- Comando: `/harness-parallel <task_graph.md>`.

---

## 4. Lista completa de 17 comandos

Comandos LEVES (5) = inline markdown, não precisa de skill wrapper.  
Comandos HEAVIES (8) = `/harness-X` no CLI do agente dispara Skill wrapper + gates obrigatórios.  
Demais (4) = medianos.

| # | Comando | Tipo | Quando usar |
|---|---|---|---|
| 1 | `/harness-spec input=<desc|ticket>` | LEVE inline | Criar/validar SPEC + approval 1-pass ANTES de qualquer dev |
| 2 | `/harness-start [--worktree <path>]` | HEAVY Skill SM | Iniciar time ÁGIL completo: gates 0→1.5 + dev tasks |
| 3 | `/harness-status` | LEVE inline | Snapshot: binding / registry / gates / tasks running-done-pending |
| 4 | `/harness-parallel <task_graph.md>` | HEAVY executor-dispatcher | Kahn waves + file locks ≥2 tasks independentes |
| 5 | `/harness-abort` | LEVE inline | Abort sessão: CANCELLED decisions + release locks |
| 6 | `/harness-skip --task Tn --reason=<x>` | LEVE inline | Skip 1 task com motivo logged decision |
| 7 | `/harness-summary [--deep]` | LEVE inline | Resumo sessão: ACs / decisions / blockers / next steps |
| 8 | `/harness-review [--worktree <p>]` | HEAVY harness-code-review | High-impact CR: só bloqueios, sem nitpicks; corrige CRIT/HIGH |
| 9 | `/harness-diff [--worktree <p>]` | HEAVY harness-diff-context | Converte diff em talking points + já committed vs to-commit. GitHub PR URL OU local worktree |
| 10 | `/harness-pr-comments <PR URL>` | HEAVY harness-pr-comments | Classifica comentários PR: válido / nitpick / inválido. + respostas pré-escritas inglês |
| 11 | `/harness-fix expected=<X> repro=<steps>` | HEAVY debugger-bugfix | Scientific debugging: hypothesize→instrument→reproduce→fix→verify |
| 12 | `/harness-manual-test <plan.md path>` | HEAVY manual-test-executor | Executa plan manual step a step via Playwright MCP + screenshots/evidence |
| 13 | `/harness-ci-fix <PR/Run URL>` | HEAVY harness-ci-fixer | Diagnose CI jobs failing → classify root cause → implement fix → rerun local confirm |
| 14 | `/harness-design <spec Figma|brief>` | HEAVY harness-social-ui-designer | UI pipeline 4 modos: social media / UI feature / Design system / Logo. Gate APROVAÇÃO EXPLÍCITA antes de executar. |
| 15 | `/harness-figma <link Figma>` | HEAVY social-ui-designer modo Figma | Coleta valores dev-mode exatos, reusa ui components existentes, implementa 1ª tentativa, auto-verifica pixel. |
| 16 | `/harness-decisions [summary|filter|tail|export] args...` | Skill harness-decisions-query | Query decisions.log.jsonl (summary PT-BR default; filter --spec SPEC-X; export csv) |
| 17 | `/harness-ship` | **HEAVY FINAL** | Último gate. Lint → fix CRIT/HIGH → sync docs AGENTS.md → **1 conventional commit** → push → **DRAFT PR** open → assign user. |

---

## 5. Contratos / Regras — ordem de leitura para aprofundar

1. **MAIOR PRECEDÊNCIA ABSOLUTA (1→17 regras):** [engineering-contracts SKILL](file:///home/laion/.trae/skills/engineering-contracts/SKILL.md) — apêndices: A conflitos hard-stop, B conventional commits, C gh-stack hierarchical PRs (≥3 tasks / >15 arquivos OBRIGATÓRIO bottom-up).
2. **Regras processo gates + scissor check:** [HARNESS_RULES.md](file:///home/laion/.trae/HARNESS_RULES.md) §🟠 BINDING + §🟡 DECISIONS LOG SEMPRE + §🟢 QUALITY/COMPLIANCE + §🟣 SPEC + §🔴 PARALELISMO.
3. **Arquitetura 13 comandos heavy vs leves:** [HARNESS_COMMANDS.md](file:///home/laion/.trae/HARNESS_COMMANDS.md).
4. **Versão curta on-the-go p/ agente:** [REFERENCE_USER_RULES_MINIFIED.md](file:///home/laion/.trae/REFERENCE_USER_RULES_MINIFIED.md) — REGRA 7 / 7.5 token reduction / 7.75 script mode / 7.8 registry JSONL / 8 SPEC+parallel.
5. **Paths + helpers oficiais (ÚNICOS writers):** [harness_sessions_contract.sh](file:///home/laion/.trae/contracts/harness_sessions_contract.sh) — 14 helpers:
   - paths: `harness_resolve_workspace_name`, `harness_resolve_worktree_slug`, `harness_compute_paths`, `harness_level2_binding_path`
   - decisions: `harness_decisions_path`, `harness_append_decision_jsonl`, `harness_migrate_decisions_md_to_jsonl`
   - registry: `harness_registry_path`, `harness_registry_append_jsonl`, `harness_registry_lookup_last`, `harness_registry_migrate_md_to_jsonl`
   - token reduction (H1-H5): `harness_tr_diff`, `harness_tr_read`, `harness_tr_collapse_blank`, `harness_tr_stdout`, `harness_tr_grep`

---

## 6. Hooks automáticos (3) — agente nem vê, roda sozinho

| # | Hook | Evento | Modo | O que faz | Bloqueia? |
|---|---|---|---|---|---|
| 1 | `pretooluse-worktree-binding.sh` | Cada tool call com path args (Read/Glob/Grep/Edit/Write/RunCommand/Delete/LS) | ENFORCEMENT | Checa `SESSION_ID → registry.jsonl LAST STATUS=BOUND.wt_root`. Scissor: path∈BOUND ou HARNESS_SESSIONS_ROOT? | **SIM exit 2 BLOCK** |
| 2 | `posttooluse-3layer-dedup.sh` | Post tool write (Edit/Write em rules/contracts/skills) | QUALITY SIGNAL | Níveis contracts ↔ user_rules ↔ skills: 3 camadas NÃO PODEM duplicar mesma regra. Detecta + sugere move p/ camada certa | No, warn-only |
| 3 | `posttooluse-lang-pt-check.sh` | Post Edit/Write em arquivo código | QUALITY SIGNAL | Heurística: 4+ stopwords PT-BR OU (2+ linhas acentos + 2 stopwords). Sinaliza agente tem que AskUserQuestion obrigatório: A Traduz inglês / B manter PT / C desabilitar NESTA sessão append flag no registry.jsonl. | No, warn-only exit 0 sempre |

Config: [hooks.json](file:///home/laion/.trae/hooks.json).

---

## 7. Melhorias recentes / changelog (últimas 72h)

Este README reflete as últimas atualizações:

### 2026-08-30 — MELHORIAS 1,2,3 + R migração registry + ITEM4 install + TS stack parcial
- **ITEM1 decisions JSONL-only (removido md):** Helper único append decisions. 2 arquivos legados md migrados. Skill `harness-decisions-query` 4 modos. 12 arquivos docs atualizados referências.
- **ITEM2 5 heurísticas token reduction:** H1 diff trim / H2 Read trunc / H3 blank collapse / H4 stdout 4000 cap / H5 grep compact. Bypass env.
- **ITEM3 MVP Script Mode DeepSeek-inspired leve:** gatilho batch≥3 → 1 script bash/node em 1 RunCommand. Sem nova infra. Workflow 3 passos + anti-padrões REGRA 7.75.
- **R registry binding JSONL-only (removido md):** 4 helpers registry unificados. 2 hooks hook1/hook3 atualizados parser JSONL python safe. 20 docs updates. 2 entries migradas; rm registry.md. Anti-padrões Edit manual proibido REGRA 7.8.
- **DOC1** = este README explicando tudo (1ª vez, ponto de entrada único).
- **ITEM4 (novidade hoje) — install script + runtime TS parcial:**
  - CLI decisions migrado python → TypeScript (tsx zero-build, strict; 4 modos 1:1 output idêntico ao Python). Arquivo legado `.py` DELETADO.
  - Runtime TS: package.json + tsconfig strict + deps `tsx@4 / typescript / @types/node` instaláveis via pnpm.
  - Install script `scripts/install-harness.sh` (bash, idempotente, `--dry-run` default, `--apply` executa; backup automático; whitelist assets; blacklist user_rules/memory/registry.jsonl nunca sobrescritos)

---

## 8. Instalação fresh (abrir Trae novo em outra máquina)

Cenário: instalação Trae limpa, sem nada em `~/.trae/`. Você tem esse harness exportado em uma pasta (zip, git clone, pendrive).

### 3 passos (KISS)

**Passo 1.** Garanta que a pasta fonte tem este harness (tem que existir `scripts/install-harness.sh`). Exemplo:
```bash
cd /caminho/para/dot-trae-exportado
ls scripts/install-harness.sh   # tem que existir
```

**Passo 2.** DRY-RUN primeiro (não mexe em nada, só mostra o que faria — OBRIGATÓRIO):
```bash
bash ./scripts/install-harness.sh --target ~/.trae
```
Exemplo output esperado:
```
==> Install harness [dry-run]
    Source: /caminho/para/dot-trae-exportado
    Target: /home/voce/.trae
    cp root: README.md ...
    cp dir : commands/ contracts/ skills/ hooks/ scripts/ permission/
```

**Passo 3.** Se dry-run OK, rodar com `--apply`:
```bash
bash ./scripts/install-harness.sh --target ~/.trae --apply
```

**O que acontece em Passo 3:**
1. 🛟 Se `~/.trae` já existir → backup automático para `~/.trae.bak-YYYYMMDD-HHMM/` (nunca perde dados existentes)
2. ✅ Copia **whitelist** (código harness versionado): commands/, contracts/, skills/, hooks/, scripts/, permission/ + arquivos raiz essenciais (package.json, tsconfig.json, README, HARNESS_*, etc)
3. 🛡 **Blacklist NUNCA copia para não sobrescrever seus dados locais:** `memory/`, `user_rules/`, `bindings/registry.jsonl`
4. 📦 Roda `corepack pnpm install` na target para baixar tsx/typescript (deps do CLI decisions TS)
5. ✔ Finaliza com checklist pós-instalação (4 checks)

### Smoke de validação pós-instalação
```bash
# 17 comandos = 17 arquivos md?
ls ~/.trae/commands/ | wc -l   # esperado 17
# CLI decisions TS funciona?
corepack pnpm --dir ~/.trae decisions --help 2>&1 | head -3
```

### FAQ install
- **Q: Posso instalar em pasta custom, não `~/.trae`?** Sim: `--target /outro/path`, mas para Trae ler o harness o padrão é `~/.trae/` como raiz de bindings/hooks/skills/commands. Use outra pasta só para exportar / preparar pacote para outra pessoa.
- **Q: Meu registry.jsonl/sessões antigas foram apagadas?** Não. A blacklist protege. Se `~/.trae` já existia, foi feito mv backup com timestamp antes.
- **Q: A whitelist copia `skills/_shared_checklists` com segredos meus?** Sim. Antes de distribuir o harness para outra pessoa, delete `skills/_shared_checklists/` se tiver conteúdo sigiloso. O install script é intencionalmente KISS e não tenta adivinhar segredos.

---

## 9. 17 comandos rápidos (cheatsheet) — agent copy-paste

```bash
# === Registry / Binding (não Edit/Write manual ===
source ~/.trae/contracts/harness_sessions_contract.sh
harness_registry_path
harness_registry_lookup_last "$SESSION_ID" | jq -r .worktree_root
harness_registry_append_jsonl "$SESSION_ID" BOUND "$WT" '{"workspace_name":"Flockr","flags":{"LANG_PT_CHECK":"ENABLED"}}'

# === Decisions (query + append ===
harness_decisions_path "$WT"
harness_append_decision_jsonl "$WT" "GATE_PASS" '{"gate":"0.3_SPEC_APPROVED","spec_id":"SPEC-X","approver":"user"}'
corepack pnpm --dir ~/.trae decisions "$(harness_decisions_path "$WT")" summary --lang pt

# === Token reduction (aplicar em outputs longos ===
git diff big.patch | harness_tr_diff           # H1
{ echo lines; wc -l; } | harness_tr_read 600  # H2
build-command 2>&1 | harness_tr_stdout        # H4
grep -R foo src | harness_tr_collapse_blank   # H3+H4
harness_tr_grep "pattern" src/ ts             # H5
```

---

## 9. O que NÃO existe (de propósito — YAGNI hard stop)

- Workflow de deployment/infra (Railway, Vercel, Terraform) ainda não como skill harness (usar skills individuais).
- Sem `run_code` transport isolado / sem worker thread `isolated-vm` (MVP Script Mode é suficiente p/ 95% casos).
- Sem SDK typescript `.d.ts` auto-gerado (não vale a pena até 2ª ordem de scripts aninhados).
- Sem UI web dashboard do harness (tudo CLI + docs).

> Para pedir feature nova: `/harness-spec input="adicionar <X> ao harness"` para criar SPEC primeiro.

---

**Autor:** Flockr Harness Team (skills 17 personas).  
**Última atualização deste README:** 2026-08-30 (após melhorias 1,2,3 + R registry).
