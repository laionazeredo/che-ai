# Che AI ☭

**Che** é um Harness de Engenharia Agêntica agnóstico a IDE, projetado para rodar dentro de assistentes de codificação de IA modernos (como Trae, Codex, Cursor, Claude Code e OpenCode).

Ele atua como um "plugin" que orquestra a IA para simular uma equipe Agile completa — incluindo Scrum Master, Engenheiro de Software, QA, Designer de UX e Oficial de Compliance. Ele impõe práticas rigorosas de Ciclo de Vida de Desenvolvimento de Software (SDLC), memória de projeto determinística, **um Politburo de Domínios Especialistas** e portões de qualidade automatizados.

## 🚀 Suporte Multi-Agente

O Che foi projetado para ser portátil entre diferentes agentes de IA. Após a instalação, ele configura automaticamente adaptadores para:
- **Trae**: Suporte nativo via diretório raiz.
- **Codex**: Comandos slash em `~/.codex/commands/` e skills em `~/.agents/skills/`.
- **Claude Code**: Comandos slash em `~/.claude/commands/` e skills em `~/.claude/skills/`.
- **Cursor**: Regras e skills integradas via `.cursor/rules/`.

Todos os agentes compartilham os mesmos **Contratos de Engenharia**, **Expert Skills do Politburo** e **Memória Durável**, garantindo uma experiência consistente independentemente da ferramenta utilizada. Dados duráveis do projeto podem ser movidos entre máquinas usando os **Comandos de Portabilidade** (`/che-export` e `/che-import`), com inclusão **opcional** dos bancos SQLite.

## 🚀 Instalação Rápida

Para instalar o Che em seu ambiente local (padrão em `~/.trae`), execute:

```bash
curl -fsSL https://raw.githubusercontent.com/laionazeredo/che-ai/main/scripts/install-che.sh | bash
```

## 🧠 Conceitos Principais

O Che é construído sobre a filosofia de que a **Engenharia Agêntica requer limites, domínios especializados e memória**.

---

### 1. Core Zero-Build

A lógica central do Che é escrita em Python puro (`che_core/`), evitando dependências pesadas de Node.js e etapas de compilação. Nenhum `package.json`, zero dependências externas (apenas stdlib — SQLite, json, tarfile, etc.). O arquivo de configuração canônico é [`pyproject.toml`](file:///home/laion/.trae/pyproject.toml).

---

### 2. 🏗️ Arquitetura Oficial de 3 Camadas (CANÔNICA, NÃO DUPLICAR)

Toda regra, skill e instrução de domínio segue um hierarquia de 3 camadas. Qualquer nova feature deve respeitar a separação abaixo (ver também [`AGENTS.md §1`](file:///home/laion/.trae/AGENTS.md)):

```mermaid
flowchart LR
    L1["L1 — Camada 1<br/>domains/<slug>/<br/>User Profiles & Runbooks<br/>Contexto humano de domínio (específico por área)"]
    L2["L2 — Camada 2<br/>CHE_RULES.md · CHE_COMMANDS.md<br/>SÓ títulos + links p/ L3 (NUNCA corpo)"]
    L3["L3 — Camada 3<br/>skills/<skill-slug>/SKILL.md<br/>Corpo REAL das regras, declarativo ≤15 linhas Python"]

    L1 -->|"Regras de domínio (engineering/ux/product...)"| L3
    L2 -->|"Roteador → linka p/ skill L3"| L3
    L3 -->|"Invoca se necessário"| CORE["che_core/ Python<br/>(lógica procedural complexa)"]
```

- **L1 — `domains/<slug>/`** *(User Profiles & Runbooks)*: Instruções específicas de cada domínio do Politburo. Cada domínio possui 5 artefatos canônicos (profile, runbook, gate thresholds, glossário, exemplos).
- **L2 — `CHE_RULES.md` + `CHE_COMMANDS.md`** *(Roteadores, NUNCA contém regras)*: Apenas títulos + links para a skill L3 correspondente. Serve de referência rápida para o agente.
- **L3 — `skills/*/SKILL.md`** *(Onde a regra realmente mora)*: Skills 100% declarativas. Se uma skill precisar de lógica procedural > 15 linhas Python, essa lógica **OBRIGATORIAMENTE** é extraída para um módulo Python em `che_core/` e invocada via CLI.

---

### 3. ☭ Politburo de Domínios Especialistas

O **Politburo** é o conjunto de 7 perfis de domínio canônicos que o Che usa para **escolher qual especialista assumir cada tarefa ao longo do SDLC**. A precedência de seleção de domínio (do mais forte para o mais fraco) é:

> 1️⃣ **Task Envelope frontmatter `domain:`** (sempre vence — hook automático em [`che-act §0.25`](file:///home/laion/.trae/skills/che-act/SKILL.md)) → 2️⃣ SPEC frontmatter `domain:` → 3️⃣ Registry L1.5 → 4️⃣ **Default = `engineering`**.

#### 🧑‍🤝‍🧑 Os 7 Domínios do Politburo (ORDEM CANÔNICA)

| # | Slug do Domínio | Papel no SDLC | Perfil Especialista Default | Comando downstream recomendado p/ este domínio |
|---|---|---|---|---|
| 1 | **`engineering`** ⭐ DEFAULT | Implementação de código, testes, lint, arquitetura técnica, deploy. | Engenheiro Sênior Full-stack | `/che-act` (implementação) / `/che-ship` (entrega) / `/che-fix` |
| 2 | **`ux`** | Design de interface/experiência, protótipos PenPot/Figma, sistemas de design, acessibilidade WCAG. | Product Designer UI/UX | `/che-design` (ou `/che-figma`) |
| 3 | **`product`** | Priorização, descoberta, escrita de PRDs, aceite de critérios, alinhamento com roadmap. | Product Manager Sênior | `/che-spec` + `/che-plan` (Linear/Jira/ClickUp) |
| 4 | **`devops`** | Infraestrutura como código, Docker, Kubernetes, Terraform, CI/CD, Vercel/Railway/AWS config. | Platform / SRE Engineer | `/che-ci-fix` / `/che-onboarding` (infra) |
| 5 | **`copywriting`** | Escrita de landing, e-mail transacional/marketing, tom de voz, i18n, documentação ao cliente. | Senior Content / Technical Writer | `/che-onboarding` (contexto) + `/che-spec` |
| 6 | **`social`** | Criativos, copys para Instagram/TikTok/LinkedIn, calendário editorial, assets sociais, campanhas. | Social Media Strategist + Designer Social | `/che-design` → modo A "Social Media" |
| 7 | **`seo-analytics`** | SEO on-page, programmatic SEO, schema, GA4/GSC, Search Console, Core Web Vitals, lighthouse audit. | SEO & Growth Analyst | `/che-xray` (audit) + `/che-review` (qualidade) |

#### Como o Politburo é usado na prática no SDLC
- Cada entrada no **Task Graph DAG** (`task_graph.md` L3) possui a **5ª coluna obrigatória `Domain`** com um slug acima.
- Cada Task Envelope (L3) tem **frontmatter obrigatório `domain:` / `expert_skills:` / `handoff_output:`**.
- Quando você roda `/che-task resume T3`, o Che lê o envelope, grava `ACTIVE_DOMAIN=<slug>` no registry e recomenda o comando slash downstream correto — e.g. domínio `ux` → `/che-design`, domínio `engineering` → `/che-act`.
- **Kahn Wave Groups**: Tarefas de domínios diferentes em ondas idênticas (indegree 0) são executáveis em paralelo por sessões distintas.

---

### 4. Skills Declarativas

Comportamentos e limites da IA são definidos em arquivos Markdown simples e declarativos (`skills/*/SKILL.md`). Python blocks dentro de SKILL.md têm limite hard de **15 linhas** — tudo que for maior vai pro `che_core/`. Exemplo de skill implementando o hook do Politburo: [`skills/che-act/SKILL.md §0.25`](file:///home/laion/.trae/skills/che-act/SKILL.md).

---

### 5. Memória Estruturada — 4 Níveis (Specflow Aligned)

O Che isola artefatos gerados em uma hierarquia clara que separa o nível **Estratégico** (Projeto) do **Tático** (Worktree).

```
~/.che-workspaces/
├── workspaces/          ← Container de Workspaces
│   └── <workspace-slug>/
│       └── <project-slug>/
│           ├── project/        ← L2: Estratégico (intent.md, roadmap.md, profile)
│           ├── _db/            ← L2: SQLite DBs (che_state.sqlite)
│           └── worktrees/      ← Container de Worktrees
│               └── <wt-slug>/  ← L3: Tático (Shared Assets)
│                   ├── task_graph.md, decisions.log.jsonl, spec_*.md
│                   ├── design/, qa/, reports/
│                   └── sessions/   ← L4: Efêmero (Logs por sessão)
├── .registry/           ← Metadados Globais (Session Bindings)
└── .trash/              ← Lixeira Canônica
```

- **L2 Projeto**: Memória durável que guarda o "Porquê" e o "Para Onde" (Specflow Phase 1 & 2).
- **L3 Worktree**: Área de trabalho compartilhada para implementação tática. Múltiplas sessões lendo o mesmo histórico.
- **L4 Sessão**: Apenas logs e dados temporários de execução.

---

### 6. 🔎 State Store (SQLite FTS5) + RAG Auxiliar

⚠️ **Regra SSOT (Single Source of Truth)**: O filesystem (`task_graph.md`, `decisions.log.jsonl`, `envelope.md`, `spec_*.md`) SEMPRE é a fonte verdadeira. **O banco SQLite é apenas um cache materializado reconstruível a qualquer momento** via `/che state rebuild-index`.

#### 6.1 State Store (FTS5 BM25) — implementado em [`che_core/state_store.py`](file:///home/laion/.trae/che_core/state_store.py)
- 4 tabelas canônicas: `tasks`, `decisions`, `specs`, `bindings` + FTS5 virtual tables para BM25 lexical scoring.
- **`/che-search`**: Full-text com BM25, fallback para `LIKE` se FTS5 não estiver compilado.
- **`/che-query`**: SQL parametrizada com `?` placeholders. **Dual safety por padrão**: (a) SQLite abre com `mode=ro` (read-only), (b) whitelist de prefixos `SELECT / EXPLAIN / PRAGMA`. Writes só aceitos com `--force` explícito.
- **`/che-sanitize`**: Purga 4 categorias independentes (`decisions_old` / `decisions_over_cap` / `bindings_old` / `tasks_done_old`). **`--dry-run` é o DEFAULT** — para realmente apagar é necessário passar explicitamente `--no-dry-run`. No final roda `VACUUM` para recuperar espaço.

#### 6.2 RAG Auxiliar Híbrido — implementado em [`che_core/rag.py`](file:///home/laion/.trae/che_core/rag.py)
O RAG é **auxiliar** (SDLC continua primário). **Sem pip install necessário** — fallback hard:
- `NoneBM25Provider`: vetores dummy unitários 8D sempre funcionam (pure stdlib). Search híbrida degenera para 100% BM25, nunca crasha.
- `AutoProvider` cadeia de fallback: `sentence-transformers` → `OpenAI env var` → `Anthropic env var` → sempre cai em `None`.
- Extensão **sqlite-vec** carrega **opcionalmente** via `enable_load_extension` try/except. Se não carregar, força `NoneBM25Provider`.
- Chunker ~512 tokens (≈ 384 palavras) com 10% overlap entre janelas.
- Build **incremental**: SHA-256 hash de cada chunk. Se o hash já existir no DB → skip (evita reprocessar doc igual).
- `/che-rag search`: score híbrido `0.4 * BM25_norm + 0.6 * Vector_norm` (ambos normalizados `[0,1]` antes do merge). Peso justo: semântica tem mais peso que lexical.

---

### 7. Portões de Qualidade Automatizados (che-ship)

Ao enviar código via `/che-ship`, o Che impõe automaticamente **4 executable gates em ordem fail-fast** antes de qualquer operação de Git:
1. **Scope + Lean 6-checks** (score mínimo 7.0)
2. **Code Review** (0 CRITICAL + ≤ 2 HIGH com auto-remediate sem perguntar)
3. **Compliance Heavy** (0 CRITICAL + 0 HIGH — segredos/PII/SQL injection)
4. **QA Minimal**: `ruff check che_core/ tests/` + `python -m pytest ...`

Só depois dos 4 aprovados: atomic conventional commits → push `--no-verify` → **Draft PR sempre (nunca abre PR pronta)** com auto-assign @me.

---

## 🔄 Fluxo SDLC Oficial: Specflow + SbE

O Che unifica a visão estratégica do [**Specflow**](https://www.specflow.com/) (Intent → Roadmap) com o rigor tático do [**Specification by Example**](https://martinfowler.com/bliki/SpecificationByExample.html) (Tasks → Execute → Refine).

```mermaid
flowchart TD
    subgraph STRATEGIC["1. Nível Estratégico (Specflow)"]
        IDEA["Ideia de Negócio"] --> INTENT["/che-architect Step 1<br/><b>INTENT.MD</b><br/>(Why / Who / Success)"]
        INTENT --> ROADMAP["/che-architect Step 2<br/><b>ROADMAP.MD</b><br/>(Phases / Feature Map)"]
    end

    subgraph TACTICAL["2. Nível Tático (SbE)"]
        ROADMAP --> SPEC["/che-spec<br/><b>SPEC_SLUG.MD</b><br/>(Behavior Examples GWT)"]
        SPEC --> PLAN["/che-plan<br/><b>Tickets (Linear/Jira)</b><br/>(BDD ACs + Collab Tags)"]
    end

    subgraph EXECUTION["3. Nível de Execução"]
        PLAN --> ACT["/che-act<br/><b>TASK GRAPH DAG</b><br/>(Parallel Implementation)"]
        ACT --> SHIP["/che-ship<br/><b>DRAFT PR</b><br/>(Storytelling Commits)"]
    end

    SHIP --> REFINE["Refinamento & Feedback<br/>(Loop p/ Roadmap/Intent)"]
    REFINE --> ROADMAP
```

### Como a Navegabilidade funciona:
1.  **Intent & Roadmap**: Criam a "Espinha Dorsal" do projeto. Estão sempre disponíveis em `$CHE_WORKSPACE_SHARED/projects/<slug>/`.
2.  **Spec-to-Roadmap**: Cada tarefa (`spec_*.md`) carrega o `roadmap_phase` no frontmatter, permitindo ao agente entender onde ela se encaixa no plano maior.
3.  **SbE Contracts**: As tabelas de comportamento (B-IDs) na SPEC são os contratos de verdade. O agente não pode "inventar" lógica; ele deve satisfazer os exemplos.
4.  **Storytelling History**: Os commits no formato CDJ (Contexto, Decisão, Justificativa) permitem que futuros agentes "leiam o passado" para tomar decisões melhores no presente.

---

## 🛠 Comandos Slash (22 heavy + 5 light)

Uma vez instalado, o Che expõe suas capacidades diretamente na interface de chat via comandos slash. Os 3 NOVOS de workspace/projeto/eject estão marcados com ✨.

### Categoria A — 22 Heavy Commands

| Comando | O que faz (resumo) | Politburo Domain Default |
|---|---|---|
| `/che-architect` | Parceiro estratégico de arquitetura de sistemas (stack, infra, segurança, compliance). | devops + engineering |
| `/che-archeology` | Infere Intent e Roadmap a partir do histórico git e PRs. | product |
| `/che-workspace [list\|create\|remove\|trash-list\|restore]` | ✨ **NOVO**: Gerencia workspaces L1 (`~/.che-workspaces/workspaces/<slug>/`). 3 safety gates + trash canônico. | engineering |
| `/che-project [list\|add\|remove\|trash-list\|restore]` | ✨ **NOVO**: Inicializa projeto L2 (scaffold `architecture.md`, `project_profile.md`, registry) atrelado a um workspace. | engineering |
| `/che-xray [worktree]` | Scan repo → gera project_profile.md 12 seções. | engineering |
| `/che-onboarding [worktree]` | Contexto humano interativo (roadmap, personas, lógica negócio). | product (+ copywriting / ux se ativado) |
| `/che-spec [input] <worktree> <project> [slug]` | Gera/valida Especificação de Execução (SPEC Approved). **Requer worktree e project.** | product |
| `/che-plan <worktree> <project> [slug]` | SPEC aprovada → tickets estruturados Linear/Jira/ClickUp com BDD ACs. | product |
| `/che-act` | ★ Central: SPEC GATE → scope capture → **Task Graph DAG (col Domain + Envelope)**. **Requer worktree e project.** | engineering (lê envelope depois) |
| `/che-parallel` | `/che-act` + force_parallel + che-executor-dispatcher (batches Kahn waves independentes). | engineering |
| `/che-ship` | 4 executable gates → atomic commits → push → Draft PR self-assigned. | engineering |
| `/che-fix` | Scientific debugging loop (hypothesize → instrument → reproduce → analyze → fix → verify). | engineering |
| `/che-review` | Revisão blocking de código (local vs origin/main ou PR URL). | engineering |
| `/che-diff` | Contexto leve sobre PR ou diff — DIFERENTE de review blocking. | engineering |
| `/che-manual-test` | Executa manual_test_plan.md passo a passo via Playwright MCP + evidências PNG. | QA (via engineering) |
| `/che-pr-comments` | Classifica e tria comentários do GitHub PR. | engineering |
| `/che-ci-fix` | Diagnóstico e fix de falha de CI GitHub Actions. | devops |
| `/che-design` · `/che-figma` | Orquestra design UI/UX ou social media via open-pencil MCP. | **ux** (default) / social |
| `/che-export [--include-db] [--db-size-limit-mb=N]` | 📦 Empacota L2+L3 para portabilidade. | engineering |
| `/che-import [--include-db]` | 📦 Restaura archive. SQLite é opcional via `--include-db`. | engineering |
| `/che-task [list\|show\|resume\|set-status]` | Multi-domain DAG task picker. Resume grava ACTIVE_* flags. | *(lê envelope domain:)* |
| `/che-query --sql "..." [--bind ...] [--force]` | SQL parametrizada no state SQLite. Read-only DEFAULT. | engineering |
| `/che-sanitize [--max-age-days=180] [--max-decisions=5000] [--dry-run]` | Purge + VACUUM. dry-run DEFAULT ON. | engineering |
| `/che-search "..." [--top-k=N] [--scope=...]` | FTS5 BM25 lexical. | engineering |
| `/che-rag [build-index\|search] [--provider=auto/none/openai/anthropic]` | RAG híbrido BM25+vetor. `none` sempre funciona (zero pip). | engineering |
| `/che-eject [plan\|trash-list\|restore]` | ✨ **NOVO**: Ejetar Che com segurança. Desinstala adapters, move whitelist para trash, limpa snippets .gitignore. | engineering |

### Categoria B — 5 Light Commands (<15 linhas, inline, não viram skill)
`/che-status`, `/che-skip`, `/che-decisions`, `/che-summary`, `/che-abort`.

---

### 📦 Portabilidade (NOVAS flags opcionais de DB)

Os comandos de portabilidade permitem que você mova o contexto e a memória de um projeto entre diferentes máquinas ou ambientes sem perder o histórico de decisões e a arquitetura definida.

#### `/che-export [worktree] [output.tar.gz] [flags]`
Empacota os dados duráveis do projeto (Níveis L2 e L3).

**Novas flags — Banco OPCIONAL (nunca padrão):**
- `--include-db` (default: **OFF**): Inclui também os bancos SQLite (`che_state.sqlite` + `che_rag.sqlite`) localizados em L2 dentro da pasta `_db/` do tar.
- `--db-size-limit-mb <N>` (default: **250**): Limite de tamanho SOMADO (todos sqlite). Se ultrapassar → DBs são **pulados**, e um arquivo explicativo `_db/SKIPPED.txt` é gravado no archive informando: threshold + tamanho real + qual comando re-exportar com limite maior.
- Se `--include-db` não for passado: o tar só tem markdown/jsonl. Tamanho geral < 1MB, super portátil.

**Exemplos:**
```bash
# Apenas metadados (default / mais comum)
/che-export /home/user/my-repo ./backup-metadata-only.che.tar.gz

# Com bancos, usando limite default 250MB
/che-export --include-db /home/user/my-repo ./backup-full.che.tar.gz

# Limite customizado de 500MB (projeto grande com muitos decisions)
/che-export --include-db --db-size-limit-mb=500 /home/user/my-repo ./backup-full-500.che.tar.gz
```

#### `/che-import [archive] [workspace_dest] [--include-db]`
Restaura um projeto a partir de um archive gerado por `/che-export`.
- **Sem `--include-db`**: apenas L2+L3 metadados. State e RAG são reconstruídos no destino via `/che state rebuild-index`.
- **Com `--include-db`**: também copia `_db/*.sqlite` de volta para a pasta CHE_PROJECT_DIR do destino. Se já houver DB com mesmo nome → resolve conflito adicionando sufixo `--import-YYYYmmdd-HHMM` (não destrói nada, não overwrita).
- Qualquer conflito de slug de projeto → sufixo timestamp não destrutivo.

---

## 🗂 Gerenciamento Determinístico Workspace (L1) + Projetos (L2)

O Che **não cria `.trae/` dentro dos seus projetos cliente**. Toda memória, arquitetura e artefatos ficam em uma **hierarquia canônica 4 níveis** em `~/.che-workspaces/`, gerenciada por comandos idempotentes e 3 safety gates iguais em toda operação destrutiva: `--dry-run` sempre default ON + `--confirmed` + `--i-know-what-im-doing` obrigatórios. NUNCA é usado `rm -rf` — tudo é movido para uma **lixeira canônica** com restore disponível.

### 🧩 O que é L1 Workspace vs L2 Projeto

| Nível | Caminho físico | O que guarda | Quando criar |
|---|---|---|---|
| **L1 Workspace** | `~/.che-workspaces/<ws-slug>/` | Agrupa N projetos de uma mesma **organização / equipe / contexto** (ex: `flockr`, `general-config`, `cliente-xpto`). | Uma vez por equipe/empresa. Normalmente você tem 2~3 workspaces no máximo. |
| **L2 Projeto** | `<L1>/<repo-slug>/project/` | Dados **duráveis** do projeto: `architecture.md`, `project_profile.md`, `registry.jsonl`, bancos SQLite L2 (`che_state.sqlite`, `che_rag.sqlite`). Sobrevive a troca de worktree. | Um por repositório cliente. Criado **antes** de rodar `/che-spec` ou `/che-act`. |
| **L3 Worktree** | `<L2>/../.wt/__<branch-slug>/` | Dados **compartilhados entre sessões** da mesma branch: `task_graph.md`, `decisions.log.jsonl`, `spec_*.md`, envelopes, `qa/`, `designs/`. Criado **automaticamente via hook PostToolUse** quando você roda `git worktree add`. | Automático — NÃO use comandos do Che para criar/remover worktrees Git (use `git worktree` canônico; o hook cuida do resto). |
| **L4 Sessão** | `<L3>/sessions/<CHE_SESSION_ID>/` | Dados **efêmeros** de uma sessão: logs, debug, payloads. | Automático — nunca exporta, nunca commita. |

### ⭐ 3 Regras de Ouro antes de usar

1. **Git worktree é canônico, não o Che.** Use `git worktree add/remove/prune` normalmente. O hook `posttooluse-3layer-dedup.py` detecta automaticamente e cria/apaga as pastas L3 correspondentes — não crie wrappers.
2. **Remoção = move para trash, nunca delete.** Todo `remove` move arquivos para `~/.che-workspaces/.trash/<kind>/<slug--timestamp>/` com manifesto. Use `restore` para voltar.
3. **3 Safety Gates em TUDO destrutivo:** `--dry-run` default ON + `--confirmed` + `--i-know-what-im-doing`. Falta um → operação bloqueada com status `blocked-safety-gates`.

---

### `/che-workspace` — Gerencia Workspaces L1

**Quando usar:** Quando você vai começar com um cliente/equipe nova e quer um container para múltiplos projetos. Ou para listar/auditar workspaces existentes.

#### Subcomandos

| Subcomando | O que faz |
|---|---|
| `list` | Lista todos workspaces ativos em `~/.che-workspaces/workspaces/` (JSON com slug, path, qtd projetos). |
| `create <nome>` | Cria workspace L1 + scaffolding vazio. Default path = `~/.che-workspaces/workspaces/<slug>/`. Idempotente. |
| `remove <nome>` | ⚠️ Destrutivo. Move workspace INTEIRO para trash (todos projetos dentro). **3 safety gates obrigatórios.** |
| `trash-list` | Lista entradas na lixeira com manifesto JSON. |
| `restore --trash-slug <slug--timestamp>` | Restaura workspace de volta da lixeira. |

#### Exemplos práticos

```bash
# 1) Listar workspaces existentes (leitura, sempre seguro)
/che-workspace list

# 2) Criar workspace para um cliente novo
/che-workspace create cliente-xpto

# 3) Remover workspace obsoleto — PRIMEIRO dry-run default
/che-workspace remove cliente-xpto
# Retorna status "dry-run" mostrando quantos arquivos/projetos seriam movidos.
# Concorda? Então desliga o dry-run + flags de confirmação dupla:
/che-workspace remove cliente-xpto --no-dry-run --confirmed --i-know-what-im-doing
```

---

### `/che-project` — Gerencia Projetos L2

**Quando usar:** Quando você clonou um repo cliente e quer **inicializar a estrutura durável L2** atrelada a um workspace L1.

#### Subcomandos

| Subcomando | O que faz |
|---|---|
| `list [--workspace <ws-slug>]` | Lista projetos de um workspace (ou todos se omitir). |
| `add <worktree-path> --workspace <ws-slug> [--name <friendly-name>]` | ⭐ Mais usado. Registra um projeto L2 no workspace informado. Se `--name` omitido, o fallback é `<workspace>--<folder>`. Valida se o workspace existe. |
| `remove <project-slug> --workspace <ws-slug>` | ⚠️ Destrutivo. Move pasta `project/` + `_db/` para trash. **3 safety gates obrigatórios.** |

#### Exemplos práticos

```bash
# 1) Adicionar um projeto L2 a um workspace existente
#    Contexto: repositório em /home/laion/code/flockr/Lumos
#    Workspace: Flockr
/che-project add /home/laion/code/flockr/Lumos --workspace Flockr
# Isto cria:
#   ~/.che-workspaces/workspaces/Flockr/github-com-Flockr-platform-Lumos/project/ (ou nome amigável)
# Fallback de nome se --name omitido: Flockr--Lumos
```

---

### 🔗 Como se encaixa no SDLC completo

```
Nova ideia ou repo cliente novo
    │
    ▼
1. /che-workspace create minha-equipe    (se workspace não existir)
    │
    ▼
2. /che-project add meu-repo \           (ASSOCIA worktree → workspace L1
                      --workspace minha-equipe \  registra L2, cria 8 artefatos)
    │
    ▼
3. git clone / git worktree add minha-feature  (USE Git canônico — hook PostToolUse
    │                                            detecta e cria L3 .wt/__minha-feature/)
    ▼
4. /che-xray → /che-onboarding → /che-spec     (agora SPEC e decisions logam
    │                                            no PROJETO CERTO, não em paths globais)
    ▼
5. /che-act → Task Graph DAG com col Domain → /che-task resume T1 → parallel
    │
    ▼
6. Terminou ciclo? git worktree remove feat-X  (hook move a pasta L3 para trash idempotente)
    │
    ▼
7. Projeto arquivado? /che-project remove ...  (move project/ + _db/ + .wt/ para trash)
```

**Resumo mental:** `/che-workspace` = **organização**, `/che-project add` = **vincular repo físico ao armazenamento durável do Che** (o binding mais crítico de todos). Sem `add` correto, os hooks L3 não encontram o destino para criar `.wt/__<branch>/` e suas sessões ficam órfãs.

> 💡 **Dica:** Se você já tem um repositório clonado e quer "adotá-lo" no Che sem perder nada, é só rodar o `/che-project add --workspace <WS>` — ele nunca toca no diretório do seu código cliente, só cria estrutura **fora** em `~/.che-workspaces/`.

---

## 🚀 Guia Rápido: Usando o Politburo + Novas Features (Ponta a Ponta)

### Exemplo 1: Feature com UX + Eng paralelas (Politburo 2 domínios)

```
1. /che-spec            # Product: escreve SPEC, domain frontmatter (engenharia no geral)
2. /che-act             # Engineering: abre task_graph.md com TODAS as tarefas + col Domain
                         # Ex: T1 UX Wireframes · T2 UX Design System · T3 Eng API · T4 Eng UI
                         # Tarefas T1 e T2 no Wave 1, T3/T4 dependem de T1 → Wave 2
3. 🟦 Sessão UX (outra janela / outra máquina):
   /che-task resume T1  # → lê envelope.domain = ux
                         # → grava ACTIVE_DOMAIN=ux no registry
                         # → recomenda: "/che-design" com contexto do envelope
4. 🟩 Sessão Eng (janela atual):
   /che-task resume T3  # → T3 depende de T1, vai bloquear até que T1 esteja DONE.
                         # → entao /che-task resume T? (pega outra task do wave)
5. Quando UX termina T1 → mark task_graph.md T1 DONE.
   /che-task resume T3  # → agora roda. envelope.domain = engineering. recomenda /che-act.
6. Terminou tudo → /che-ship → gates → commit → push → Draft PR.
```

### Exemplo 2: State Store em 4 comandos

```bash
# 1. Reconstroi indice SQLite FTS5 a partir do filesystem (SSOT).
/che state rebuild-index /home/laion/.trae

# 2. Query parametrizada READ-ONLY (padrão, seguro)
/che-query --sql "SELECT id,domain,status FROM tasks WHERE domain = ? ORDER BY id" \
           --bind ux \
           --worktree-root /home/laion/.trae

# 3. Busca lexical full-text com BM25
/che-search "sanitize dry-run SQLite" --top-k=10 --scope=decisions

# 4. Sanitize (DRY-RUN DEFAULT: NÃO apaga nada, só mostra o que APAGARIA)
/che-sanitize --max-age-days 365 --max-decisions 2000
# Depois, se você concordar com o planejado:
/che-sanitize --max-age-days 365 --max-decisions 2000 --no-dry-run
```

### Exemplo 3: RAG zero-deps sem precisar instalar NADA

```bash
# Build index inicial (SHA256 hash por chunk, roda incremental depois)
/che-rag build-index /home/laion/.trae --provider=none   # none sempre funciona sem pip

# Search híbrida (mesmo sem vetores: cai 100% BM25, nunca crasha)
/che-rag search "arquitetura 3 camadas Politburo" --provider=none --top-k=5

# Se você tem API key OpenAI no env: auto tenta e cai em none se falhar
/che-rag build-index --provider=auto
```

---

## 🏗 Contribuição e Arquitetura

Se você é um agente de IA ou desenvolvedor querendo estender o Che, por favor leia o **[AGENTS.md](./AGENTS.md)** primeiro. Ele descreve a Arquitetura de 3 Camadas em detalhe, a regra do core em Python (zero bash para lógica), o sistema de hooks Python e como manipular o filesystem L1-L4 com segurança.

### Fluxo de Aprovação e Contribuição
Para garantir a estabilidade e segurança do framework, o Che impõe um fluxo de contribuição rigoroso:
- **Proteção de Branch**: Pushes diretos na `main` são bloqueados. Todas as alterações devem ser enviadas via Pull Requests.
- **Code Owners**: O arquivo `.github/CODEOWNERS` exige revisão e aprovação explícita de `@laionazeredo` antes que qualquer PR possa ser mergeada.
- **Política Zero-Build**: Sem dependências de Node.js (`package.json`) ou etapas complexas de build. O core é Python puro. Bash é estritamente reservado para os scripts de bootstrap/instalação.
- **Higiene da Worktree**: Scripts temporários, logs e arquivos não rastreados não devem ser deixados na raiz do repositório. Dados efêmeros pertencem às pastas de Nível de Sessão (L4).

## 🛡️ Qualidade e Segurança

O Che emprega um pipeline de Integração Contínua (CI) robusto via GitHub Actions para manter a qualidade do código e prevenir regressões de segurança:
- **Linting e Formatação**: O código Python é estritamente lintado e formatado usando `ruff`. Arquivos Markdown são validados com `markdownlint-cli2`.
- **Testes de Unidade e Segurança**: `pytest` roda testes de unidade para a lógica central (ex: resolução de caminhos, task graph, state store, portabilidade) e executa análise estática de segurança (`test_skill_security.py`) nos arquivos `SKILL.md`. Isso garante que nenhum comando Bash destrutivo (como `rm -r`, `curl`, `eval`) seja embutido em Markdown e limita blocos Python a um máximo de 15 linhas, forçando a lógica complexa para o pacote `che_core`.
- **Escaneamento de Segredos**: `TruffleHog` roda em cada push e PR para prevenir commits acidentais de segredos, chaves de API ou senhas por agentes de IA.

## 🔄 Atualizando

Para buscar a versão mais recente do Che:

```bash
curl -fsSL https://raw.githubusercontent.com/laionazeredo/che-ai/main/scripts/update-che.sh | bash
```
