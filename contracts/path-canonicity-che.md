# CONTRATO DE CANONICIDADE DE PATHS — CHE

> Single source of truth para a estrutura hierárquica L1→L2→L3→L4 do `CHE_WORKSPACES_ROOT`.
> Helper bash correspondente: `che_compute_paths` + `che_ensure_session_dirs` em `che_sessions_contract.sh`.
> Invariantes: NUNCA quebre estes contratos. Se precisar evoluir, atualize PRIMEIRO este arquivo, DEPOIS os helpers bash, POR ÚLTIMO as skills.

---

## 0. VARIÁVEIS DE AMBIENTE CANÔNICAS

| Env | Default | Valores válidos | Propósito |
|-----|---------|-----------------|-----------|
| `CHE_WORKSPACES_ROOT` | `$HOME/.che-workspaces` | Qualquer path absoluto existente com permissão write | **Raiz de TUDO** do Che (workspaces L1). Fallback compat 1-release: se novo path NÃO existir E antigo `$HOME/code/harness-sessions` existir → reutiliza o antigo. |
| `CHE_HOST_IDE` | `trae` | `trae`, `codex`, `cursor`, `claude-code`, `opencode` | Identificador do host IDE agnóstico. Adapters futuros em `adapters/<host_ide>/`. |
| `CHE_SESSION_ID` | (fallback 3 níveis: `CHE_SESSION_ID` → `HARNESS_SESSION_ID` → `SESSION_ID` → `slug-safe-date`) | UUID / slug-safe session id | Identificador ÚNICO da sessão do agente. Mesmo valor usado no Level 1 registry JSONL. |
| `CHE_HOME` | `$HOME/.trae` | Qualquer path absoluto com `skills/` + `contracts/` + `commands/` + `domains/` | Raiz do **config repo** (skills, regras, comandos). Não confundir com CHE_WORKSPACES_ROOT (dados usuário). |

---

## 1. HIERARQUIA L1→L2→L3→L4 (DIAGRAMA)

```
CHE_WORKSPACES_ROOT ($HOME/.che-workspaces/)  ← L1 — WORKSPACE (IDE workspace = conjunto de repos)
│
├─ manifesto48/                                 ← L1 EXEMPLO: nome do workspace (1 conjunto de projetos/repos)
│  │
│  ├─ vc-educar-corp-website/                  ← L2 — PROJECT (1 repo git, slug-safe nome)
│  │  │
│  │  ├─ .project/                              ← L2-PERENE: TUDO que dura ENTRE worktrees e ENTRE sessões
│  │  │  ├─ xray.md                             ←   raio-X do projeto (stack, entrypoints, idiomas, testes, CI, DB)
│  │  │  ├─ architecture.md                     ←   diagrama arquitetural + decisões perenes (Fora RADAR)
│  │  │  ├─ roles.md                            ←   papéis, stakeholders, PM, design, dev, owner GitHub/Linear
│  │  │  ├─ decisions/                          ←   ADRs arquiteturais (registro Fora RADAR)
│  │  │  ├─ onboarding.md                       ←   passo-a-passo onboarding dev novo (setup, seeds, login)
│  │  │  ├─ product/                            ←   docs produto, PRDs, roadmap (Fora RADAR)
│  │  │  └─ _legacy_uncategorized/              ←   ⛑️ ITENS NÃO CLASSIFICADOS (origem antiga harness-sessions
│  │  │                                            NÃO DELETAR. Manter 1 release, depois revisão humana.)
│  │  │
│  │  ├─ __main/                                ← L3 — WORKTREE (branch default = main). Sempre prefixo __ para branches.
│  │  │  │
│  │  │  ├─ .wt/                                ← L3-SHARED: TUDO compartilhado ENTRE sessões NA MESMA worktree
│  │  │  │  ├─ decisions.log.jsonl              ←   log de decisões desta worktree (append único, via helper)
│  │  │  │  ├─ envelopes/                       ←   TASK ENVELOPES (gabaritos SM→Dev) desta worktree
│  │  │  │  ├─ gh_stack/                        ←   gh-stack plan + PRs (#1,#2,#3 stack hierárquico)
│  │  │  │  ├─ reports/                         ←   reports compartilhados (QA, scope-check, code-review audit,
│  │  │  │  │                                     compliance scan, merge audit) com data YYYY-MM-DD prefix
│  │  │  │  ├─ specs/                           ←   SPEC files aprovados (.md + YAML frontmatter machine-parsable)
│  │  │  │  ├─ state.jsonl                      ←   pointer "qual session está ativa nesta worktree"
│  │  │  │  ├─ qa/                              ←   fixtures QA compartilhadas, seed data, evidence duráveis
│  │  │  │  └─ designs/                         ←   artefatos design compartilhados (export OpenPencil, tokens)
│  │  │  │
│  │  │  └─ sessions/                           ← L4 — SESSIONS (cada pasta = 1 sessão do agente)
│  │  │     │
│  │  │     ├─ 6a981dc48684a64a52ebd487/       ← L4 EXEMPLO: 1 session id (slug-safe UUID/date)
│  │  │     │  ├─ manifest.json                  ←   METADADOS: session_id, worktree_path, user_prompt,
│  │  │     │  │                                   started_at, status, CHE_HOST_IDE, commit hash início fim
│  │  │     │  ├─ debugger/                      ←   debugger: stack traces, reproduções, hipóteses
│  │  │     │  ├─ diffs_context/                 ←   diffs conversation brief, PR context extraído
│  │  │     │  ├─ execution/                     ←   comandos shell executados + outputs + exit codes
│  │  │     │  ├─ gh_stack/                      ←   gh_stack artefatos desta sessão (se houver)
│  │  │     │  ├─ qa/                            ←   QA desta sessão: evidências efêmeras, screenshots
│  │  │     │  │                                    (política TTL 30d: policies do harness/qa skill)
│  │  │     │  ├─ reports/                       ←   reports desta sessão (efêmeros, cópia em .wt se durável)
│  │  │     │  └─ decisions.log.jsonl            ←   decisions desta sessão (append; também duplicados
│  │  │                                             em .wt/decisions.log.jsonl via helper = single writer)
│  │  │
│  │  └─ feat-FLO-513--Process-a-refund/        ← L3 EXEMPLO: worktree feature branch (mesma estrutura __main acima)
│  │     ├─ .wt/                                 ← L3-SHARED desta worktree específica (decisions, envelopes, reports)
│  │     └─ sessions/                           ← L4 sessions APENAS desta worktree
│  │
│  ├─ outro-projeto-xyz/                        ← L2 OUTRO PROJECT dentro do mesmo workspace manifesto48
│  │  ├─ .project/                               ← L2-PERENE
│  │  └─ __main/                                 ← L3 + L4
│  │
│  └─ .migration_reports/                       ← L1-OPCIONAL: migration reports de quando este workspace foi movido
│     └─ 2026-09-03_migration_manifesto48.md
│
└─ flockr/                                       ← L1 OUTRO workspace: conjunto de repos Flockr (Lumos etc.)
   └─ Lumos/                                     ← L2 PROJECT Flockr Lumos repo git
      ├─ .project/
      ├─ __main/
      └─ feat-FLO-732--Create-dedicated-S3/
```

---

## 2. INVARIANTES (NÃO NEGOCIA — HARD FAIL)

### 2.1. Invariantes de camada
| # | Invariante | Exemplo de VIOLAÇÃO (proibido) |
|---|-----------|--------------------------------|
| I1 | **Sessões SEMPRE ficam dentro de uma L3 worktree.** | Criar `sessions/` diretamente dentro do L2 project ou L1 workspace = FAIL. |
| I2 | **Info perene (xray, arquitetura, papeis) fica em L2 `.project/` FORA de qualquer worktree.** | Colocar `architecture.md` dentro de `__main/.wt/` = FAIL (vai sumir se apagar a worktree). |
| I3 | **Info compartilhada NA MESMA worktree fica em L3 `.wt/`.** | Colocar `decisions.log.jsonl` dentro de 1 sessão específica = FAIL (outras sessões não veem). |
| I4 | **Nome de worktree branch = `__<branch-slug-safe>` (DOIS underscores prefixo).** Branch `main` → `__main`. Branch `feat/FLO-513/refund` → `feat-FLO-513--refund` (com DOIS traços substitui `/`, DOIS underscores prefixo). | Criar pasta `main/` sem prefixo `__` = FAIL. |
| I5 | **NÃO existe pasta chamada `workspace/` (colisão semântica IDE L1 workspace).** Duráveis worktree usam `.wt/`. | Qualquer path com nome literal `workspace/` no nível L2/L3 = FAIL. |
| I6 | **NUNCA delete `.project/_legacy_uncategorized/` (1 release retenção mínima).** | `rm -rf` items uncategorized automaticamente = FAIL. Requer revisão humana. |
| I7 | **Migration SEMPRE NÃO DESTRUTIVA (apenas `mv -n`, nunca `cp -r` depois `rm -rf`).** | Copiar tudo, depois deletar a pasta antiga de uma vez = FAIL. Princípio 0 perda. |
| I8 | **Paths nunca tem espaços ou caracteres unicode.** Slug-safe sempre: `[a-z0-9._-]`, espaço → `-`, maiúsculo → minúsculo. | Nome pasta `Minha Proposta/` com espaço = FAIL. |

### 2.2. Invariantes de helpers bash
| Função | Precondição | Pós-condição |
|--------|-------------|--------------|
| `che_compute_paths WORKTREE_ROOT SESSION_ID CWD` | Os 3 args são absolutos/slug-safe. | Retorna 12 variáveis `CHE_L1_*`, `CHE_L2_*`, `CHE_L3_*`, `CHE_L4_*` canônicas. |
| `che_ensure_session_dirs` | $WORKTREE_ROOT existe. | Cria `.wt/` com 7 subdirs + `sessions/<ID>/` com 6 subdirs. NUNCA sobrescreve nada existente (`mkdir -p`). |
| `che_append_decision_jsonl` | $SESSION_ID válido. | **Append em DUAL LOCATION**: (a) `.wt/decisions.log.jsonl` (single writer shared worktree); (b) `sessions/<ID>/decisions.log.jsonl` (cópia session-specific). Schema v1 fixo. |

---

## 3. CONVERSÃO SLUG-SAFE PARA NOMES (HELPER BASH: `che_slug_safe`)

Algoritmo (12 regras, idempotente):
1. Unicode → ASCII translit (se `iconv` disponível, senão remove)
2. Minúsculas tudo
3. Espaço ` ` → `-`
4. Barra `/` → `--` (DOIS traços = indica branch hierarquia)
5. `_` → mantém (exceto underscore inicial reservado sistema)
6. Qualquer caractere fora `[a-z0-9._-]` → remove
7. `--+` múltiplos → reduz para 1 `--`
8. `-+` múltiplos → reduz para 1 `-`
9. Remove `-` `.` no início e no final
10. Branch default `main` SEMPRE converte para `__main` (DOIS underscores prefixo, I4)
11. Workspace nome: se vier de IDE (TRAE workspace name), aplica slug safe
12. Project nome: se vier de repo git `owner/repo` → extrai `repo` + aplica slug safe

Exemplos:
| Entrada | Saída slug-safe |
|---------|-----------------|
| Workspace "Manifesto 48 Projetos" | `manifesto-48-projetos` |
| Repo `vc-educar/corp-website` | `vc-educar-corp-website` |
| Branch `main` | `__main` |
| Branch `feat/FLO-513/process refund` | `feat-FLO-513--process-refund` |

---

## 4. BACKWARD COMPATIBILIDADE (1 RELEASE MÍNIMA)

### 4.1. Fallback CHE_WORKSPACES_ROOT raiz
Lógica no helper (che_sessions_contract.sh L49-73):
```bash
if [ -z "$CHE_WORKSPACES_ROOT" ]; then
  if [ -d "$HOME/.che-workspaces" ]; then
    CHE_WORKSPACES_ROOT="$HOME/.che-workspaces"
  elif [ -d "$HOME/code/harness-sessions" ]; then
    CHE_WORKSPACES_ROOT="$HOME/code/harness-sessions"   # FALLBACK GRADUAL MIGRATION
  else
    CHE_WORKSPACES_ROOT="$HOME/.che-workspaces"          # DEFAULT NOVO, vai ser criado primeiro uso
  fi
fi
```

### 4.2. Estrutura antiga (harness-sessions) "espúria" — como é lida
Se o usuário ainda não migrou um workspace (ex: `manifesto48/` está no fallback `$HOME/code/harness-sessions` com a estrutura BAGUNÇADA antiga):
- Skills primeiramente **TENTAM** ler da estrutura NOVA L1-L4 (`.project/`, `.wt/`, `sessions/<ID>/`).
- Se falhar (estrutura nova não existe), **CAI PARA LEITURA DA ESTRUTURA ANTIGA** (compat mode).
- **NUNCA escreve na estrutura antiga** em compat mode — primeiro executa a migration G3 item-a-item (pedir confirmação user se estrutura antiga for detectada).

### 4.3. Keys registry JSONL legado (dual-read)
No Level 1 registry (`che_registry_append_jsonl`), **as duas keys são escritas e lidas**:
```json
{
  "che_session_dir": "/home/laion/.che-workspaces/manifesto48/proj/__main/sessions/123",
  "harness_session_dir": "/home/laion/code/harness-sessions/manifesto48/proj/sessions/123"   // compat legado
}
```
Leitura: tenta `che_*` primeiro, se não existir tenta `harness_*` (1 release).

---

## 5. MIGRAÇÃO (G3 manifesto48 — PROCESSO OFICIAL)

Ordem NÃO NEGOCIÁVEL (0 perda, rollback simples):

| Passo | Ação | Comando / Log |
|-------|------|---------------|
| M1 | LS profundo antigo workspace → arquivo texto. | `find /harness-sessions/manifesto48 -maxdepth 6 \| sort > /tmp/pre-migration-filelist.txt` |
| M2 | Classificação CSV A/B/C cada item: | 3 colunas: `path_original \| CATEGORIA \| path_novo_destino` |
| | **A = .project (L2 perene)** | xray.md, architecture.md, roles/, product/, decisions/ perenes, onboarding.md |
| | **B = .wt (L3 shared worktree)** | decisions.log.jsonl, envelopes/, gh_stack/, reports/ COMPARTILHADOS, specs/, designs/, qa durável |
| | **C = session-specific (L4)** | tudo dentro sessions/<ID>/, debugger, diffs_context, execution, reports efêmeros |
| | **UNCATEGORIZED** | item que não cai em nenhum A/B/C → `.project/_legacy_uncategorized/<caminho-original-mantido>` |
| M3 | mkdir estrutura NOVA VAZIA. | `mkdir -p` L1→L2→L3→L4 (.project + __main/.wt + __main/sessions — NÃO move nenhum arquivo ainda) |
| M4 | Loop CSV cada linha → `mv -n ORIGEM DESTINO`. | Log em `.migration_reports/2026-09-03_migration_manifesto48.csv` a cada item (status: OK/JÁ_EXISTIA/SKIP). |
| M5 | `rmdir` (apenas diretórios VAZIOS) nas pastas antigas (`workspace/`, `sessions/` do projeto antigo). | Se `rmdir` FALHAR (tem arquivos que ninguém classificou em M2) → **TUDO que sobra** move para `.project/_legacy_uncategorized/` com estrutura de subdiretórios ORIGINAL intacta. |
| M6 | Escreve relatório final md com counts A/B/C/UNCAT + comando rollback. | Arquivo: `.migration_reports/YYYY-MM-DD_migration_<workspace-name>_report.md` |
| M7 | Comando ROLLBACK documentado (se deu ruim): | `rsync -a --remove-source-files $NOVO $ANTIGO` (1 comando, desfaz tudo — item-a-item volta original). |
