---
name: "harness-xray"
description: "Onboarding raio-X de repositório NOVO. Detecta stack, linguagem, estrutura monorepo vs single, convenções de pastas, padrões de código, testes, CI, DB, serviços. Gera 12-seção project_profile.md persistido no registry global do projeto (Nível 1.5) e popula metade de architecture.md automaticamente via graphify. Usar PRIMEIRA VEZ que o harness toca num repo. Idempotente: rerun para refresh."
---

# Harness X-Ray — Repo Onboarding Raio-X

> **SHARED REFERENCES (CANONICAL — NÃO DUPLICAR corpo aqui):**
> - Full engineering contracts (precedence 1-18, DbC, KISS, No Accidental Complexity, Ousterhout): `engineering-contracts` skill
> - Path resolution + project registry Nível 1.5 helpers: `source "${HARNESS_HOME:-$HOME/.trae}/contracts/harness_sessions_contract.sh"`
> - Knowledge graph AST: `/harness-graph refresh` (wrapper graphify CLI pipx: `graphifyy`)
> - Complemento humano contexto produto: `/harness-project-knowledge`

## 0. WHEN TO CALL

**EXATAMENTE 1 VEZ por PROJETO (não por worktree, não por sessão):**
- Primeira vez que o harness encosta neste repositório (qualquer worktree)
- Ou refresh explícito quando arquitetura mudar muito (ex: migrou monolito → monorepo, trocou framework)

**NON-GOALS (não usa X-Ray):**
- Não é task spec → use `/harness-spec`
- Não é contexto humano do produto → use `/harness-project-knowledge`
- Não é conhecimento em tempo real de diff → use `/harness-diff`

---

## 1. PREFLIGHT (obrigatório antes de qualquer scan)

```bash
# 1. Carrega contracts helpers
HARNESS_HOME="${HARNESS_HOME:-$HOME/.trae}"
source "$HARNESS_HOME/contracts/harness_sessions_contract.sh"
WORKTREE_ROOT="${WORKTREE_ROOT:?WORKTREE_ROOT obrigatório para xray}"
XRAY_SESSION_ID="$(harness_current_session_id)"
XRAY_SESSION_ID="${XRAY_SESSION_ID:-xray-standalone-$(date -u +%Y%m%d-%H%M%S)}"
harness_compute_paths "$WORKTREE_ROOT" "$XRAY_SESSION_ID" "$PWD"
harness_ensure_session_dirs "$WORKTREE_ROOT"

# 2. Double-guard: registry NÃO pode cair dentro worktree
harness_assert_outside_worktree "$HARNESS_SESSION_DIR" "$WORKTREE_ROOT" "HARNESS_SESSION_DIR"
harness_assert_outside_worktree "$HARNESS_WORKSPACE_SHARED" "$WORKTREE_ROOT" "HARNESS_WORKSPACE_SHARED"
[ -n "${HARNESS_PROJECT_DIR:-}" ] || { echo "[harness-xray] ❌ HARNESS_PROJECT_DIR não resolvido (compute_paths falhou?)" >&2; exit 99; }
harness_assert_outside_worktree "$HARNESS_PROJECT_DIR" "$WORKTREE_ROOT" "HARNESS_PROJECT_DIR (registry Nível 1.5)"
mkdir -p "$HARNESS_PROJECT_DIR"

# 3. Constrói UMA VEZ os 3 paths de output do registry Nível 1.5 via helper type=project_registry
XRay_RELATED_ID="xray-${HARNESS_PROJECT_SLUG:-unknown}"
XRAY_PROJECT_PROFILE_PATH="$(harness_output_path "project_registry" "project-profile" "${HARNESS_PROJECT_SLUG:-unknown}" "workspace" "md")"
XRAY_ARCHITECTURE_PATH="$(harness_output_path "project_registry" "architecture" "${HARNESS_PROJECT_SLUG:-unknown}" "workspace" "md")"

# Se helper criou abaixo workspace_shared mas registry canônico = HARNESS_PROJECT_DIR → use o canônico
XRAY_PROJECT_PROFILE_PATH="${HARNESS_PROJECT_DIR}/project_profile.md"
XRAY_ARCHITECTURE_PATH="${HARNESS_PROJECT_DIR}/architecture.md"

# 4. Verifica graphify CLI disponível. Como harness-graph agora joga cache FORA worktree,
#    o output de /harness-graph refresh cai em $HARNESS_WORKSPACE_SHARED/graphify/<id>/
if ! command -v graphify >/dev/null 2>&1; then
  echo "[harness-xray] ⚠️  graphify CLI NÃO instalado. Instalar: pipx install graphifyy (double 'y')"
  echo "[harness-xray] Prosseguindo com scan fallback leve (sem graph knowledge graph)"
  GRAPHIFY_OK=0
else
  GRAPHIFY_OK=1
fi
```

### 1.1 Escrevendo artefatos do registry (3 outputs)

**NÃO FAÇA write manual `cat > arquivo` dentro worktree.** Em §2 Passo 7, os 3 artefatos devem:

```bash
# 7a. project_profile.md → write atômico FORA worktree
{
  # ... conteúdo 12-seções template §2.7a ...
} | harness_write_file_atomic "$XRAY_PROJECT_PROFILE_PATH"

# 7b. architecture.md (hybrid auto+manual) → write atômico FORA worktree
{
  # ... conteúdo template §2.7b ...
} | harness_write_file_atomic "$XRAY_ARCHITECTURE_PATH"

# 7c. Audit trail append → helper oficial (NÃO echo >> registry.jsonl manual)
harness_append_decision_jsonl "XRAY_SCAN" "{\"project_slug\":\"${HARNESS_PROJECT_SLUG:-unknown}\",\"graphify_used\":${GRAPHIFY_OK},\"files_scanned\":${FILES_SCANNED:-0},\"stack_version\":\"2026-09-01\"}"
```

---

## 2. 7-PASSO SCAN PIPELINE (ordem fixa)

### Passo 1 — Graphify first (se CLI disponível, ~15s)
```
/graphify refresh          # gera graphify-out/ no worktree (gitignored)
/graphify stats            # extrai contagem símbolos, linguagens, arquivos
/graphify query "quais sao os entry points deste projeto? onde fica a camada de dados? onde ficam os testes?"
```
Extrai automaticamente do graph output:
- entry points (Next.js apps, package.json main, server.ts, main.py)
- data layer tables/entities/repositories
- test framework detection (Vitest/Jest/Pytest)
- dependency graph hubs (módulos mais importados)

### Passo 2 — Fallback lightweight AST scan (se GRAPHIFY_OK=0)
Alternativa sem graphify (grep + Glob heurísticas):
- `*Glob **/*.{ts,tsx,py,rs,go,java,rb}` → top 3 extensões por contagem → linguagem primária
- `Glob package.json  pyproject.toml  Cargo.toml  go.mod  pom.xml  build.gradle` → build system
- `Glob docker-compose.yml  compose.yml  .env.example  docker/` → infra containers
- `Glob .github/workflows/*  .gitlab-ci.yml  .circleci/*  nx.json  turbo.json` → CI/orquestrador
- `Glob **/migrations/  **/prisma/schema.prisma  supabase/migrations/*` → DB layer

### Passo 3 — Estrutura + monorepo detection
Classifica em:
- `SINGLE-REPO` (1 app): existe 1 único package.json na raiz
- `PNPM-MONOREPO-WORKSPACES`: `pnpm-workspace.yaml` na raiz + `packages/`
- `NPM-MONOREPO-WORKSPACES`: root package.json `"workspaces": []`
- `NX-MONOREPO`: `nx.json` na raiz
- `TURBOREPO`: `turbo.json` na raiz
- `POETRY/WORKSPACES` Python: `workspaces = true` em pyproject.toml
- `UNKNOWN-CUSTOM` se múltiplos apps em pastas `apps/*/src`

Extrai:
- Número de apps e packages
- Nome de cada package (e escopo `@org/pkg` se tiver)
- Convenção de pastas canônicas detectadas: `src/`, `app/`, `pages/`, `components/`, `services/`, `repositories/`, `lib/`, `db/`, `tests/`

### Passo 4 — Stack tecnológica (auto-detect)
Preenche tabela stack 10 categorias:
| Categoria | Auto-detect sources |
|---|---|
| Linguagem primária | % arquivos .ts/.py/.rs/.go + package.json engines |
| Frontend framework | next/react/vue/angular/svelte em dependencies |
| Backend framework | nest/express/fastify/django/fastapi/actix/gin/spring |
| Database driver | pg/postgres prisma typeorm sqlite mysql redis neo4j |
| Auth provider | next-auth supabase-auth auth0 clerk jwt |
| Payment (se houver) | stripe braintree paypal mercadopago |
| Testing framework | vitest jest playwright cypress pytest pnpm test: |
| Lint/format | biome eslint prettier ruff black gofmt |
| CI/CD provider | .github → GitHub Actions; .gitlab → GitLab CI; railway.json → Railway; vercel.json → Vercel |
| Deploy target | vercel.json → Vercel; railway.json → Railway; Dockerfile + k8s manifests → K8s; terraform → TF provider |

### Passo 5 — Convenções de código + padrões
Auto-detecta (heurísticas grep + glob):
- **Import strategy**: `tsconfig.json` tem `paths:`? → `@/` alias; `moduleResolution:"bundler"`? → `exports` field
- **Arquitetura 3 camadas?** Existem arquivos `*Router.* + *Service.* + *Repository.*` em ≥2 lugares → Router→Service→Repository pattern
- **Colocação de testes**: `tests/` global OU `__tests__/` colocado OU `*.test.ts` lado a lado?
- **Env var parsing**: existe `zod` + schema? → safe parsing validado; `.env.example` existe?
- **Logger estruturado?** Procura por `pino`, `winston`, `bunyan`, `@flockr/logger` pattern de fields OTel
- **Convenção commits**: `.husky/commit-msg`? → conventional; `cz`/commitlint config?
- **i18n** (se houver): `next-intl`, `i18next` messages dirs detectados?

### Passo 6 — Riscos arquiteturais óbvios (red flags para scrum master)
Marca SIM/NÃO + 1 linha evidência:
| Red flag | Onde procurar |
|---|---|
| ⚠️ God package único ≥1k arquivos | 1 package só contém tudo |
| ⚠️ Circular imports suspeitos | graphify cycle detection ou grep `from "../"` em profundidade |
| ⚠️ Raw SQL sem migração | `.execute()` em arquivos `.ts` que não estão em migrations/ |
| ⚠️ No teste unitário detectado | 0 arquivos `*.test.*` em project inteiro |
| ⚠️ Secrets hardcoded (HEURÍSTICA) | grep `sk_`, `-----BEGIN RSA`, `NEXT_PUBLIC_SECRET` — avisa não executa action |
| ⚠️ Hard-coded environment URLs | grep `http://prod.` / `app.<tld>` sem .env |

### Passo 7 — Gera arquivos no registry Nível 1.5
Escreve 3 artefatos **ABAIXO de `$HARNESS_PROJECT_DIR/`** (compartilhado worktrees):

#### 7a. `project_profile.md` — OBRIGATÓRIO, 12 SEÇÕES FIXAS
```markdown
---
project_slug: <HARNESS_PROJECT_SLUG>
generated_at: <ISO8601 UTC>
xray_version: 1
worktree_root_at_scan: <ABS_PATH>
git_origin_url_at_scan: <ORIGIN_URL or "N/A local">
graphify_used: true|false
---

# Project Profile — <slug>

## 1. Repo Classification
- Estrutura: SINGLE-REPO | PNPM-MONOREPO | NX-MONOREPO | etc
- Número de apps detectados: N
- Número de shared packages detectados: N

## 2. Stack Tecnológica (auto-detect)
| Categoria | Ferramenta(s) detectadas |
|---|---|
| Linguagem | ... |
| Frontend | ... |
| (continua as 10 categorias acima) |

## 3. Shared Packages (se monorepo — tabela nome→propósito→path relativo)
| Package | Public exports entry points | Propósito inferido | Risco de alteração (1-5) |
|---|---|---|---|
| `@scope/db` | `., ./qrcode` | Entidades + QR | 5 = alto impacto cross-app |

## 4. Convenções de Pastas Canônicas
```
root/
├── apps/
│   ├── platform/    → Next.js RSC public + admin
│   └── scanner/     → Next.js PWA scanner
└── packages/
    ├── db/          → data layer
    └── ui/          → componentes compartilhados
```

## 5. Entry Points Principais
- App A: `apps/platform/src/server.ts` (porta 3000, Next.js standalone)
- App B: `packages/scanner/src/pages/_app.tsx` (export padrão)

## 6. Camada de Dados Detectada
- ORM/Query builder: TypeORM v0.3.x / Prisma v5 / ...
- Migrations path: `packages/db/src/migrations/*.ts`
- Entities principais (top-5 por referências no graph): Order, Ticket, User, Event, Refund
- RLS (Row Level Security): Supabase enabled? SIM/NÃO + tabelas

## 7. Auth & Security Model
- Strategy: NextAuth (Auth.js) v5 / Supabase Auth / Clerk / ...
- Session store: Cookie JWT | DB sessão | Redis
- PII data where: tabelas com email, phone, address fields listadas

## 8. Testing Stack (onde ficam os testes, como rodar)
- Unit test framework: Vitest (pnpm vitest run)
- E2E framework: Playwright (CI=1 pnpm test:e2e)
- Coverage: `--coverage` → cobertura mínima? (se detectado)

## 9. CI/CD Pipeline Detectada
- Provider: GitHub Actions
- Arquivos principais: `.github/workflows/ci.yml` (build+typecheck+test), `.github/workflows/deploy.yml`
- Deploy targets: Vercel (apps: platform + scanner) / Railway / K8s

## 10. Padrões Arquiteturais Detectados
- Router → Service → Repository: SIM (>=2 locais) | NÃO
- Composition patterns: React hooks + context providers | Compound components detectados?
- Observability: Structured logger (pino + trace_id) | Logs estruturados OTel?

## 11. Red Flags Arquiteturais (Passo 6)
| Red flag | Evidência | Ação sugerida primeiro contato |
|---|---|---|
| (ex: God package) | `packages/db` 2.3k arquivos, tudo lá | Split em subpackages quando touchar |

## 12. Knowledge Graph Index (se graphify)
- graphify-out/GRAPH_REPORT.md existe? SIM
- Hubs de importação top-5:
  1. `@scope/db/src/index.ts` (importado 142 vezes)
  2. `@scope/trpc/src/client.ts` (importado 89 vezes)
  3. ...
```

#### 7b. `architecture.md` — PRÉ-PREENCHE metade AUTOMÁTICA, deixa resto HUMANO
```markdown
# Architecture — <slug>

## ⚙️ Auto-populated by harness-xray (NÃO editar esta seção manualmente)
- Project Profile: [project_profile.md](./project_profile.md)
- Estrutura detectada: ...
- Stack: ...
- Entry points: ...
- Data layer: ...

## 🧭 Manual Part — PREENCHER via /harness-project-knowledge
### Arquitetura Geral (desenho mental: 1 página)
### Diagrama de Contexto C4 (Level 1: sistemas externos + este)
### Diagrama de Container C4 (Level 2: apps + DB + cache + filas)
### Componentes Principais (Level 3: módulos cross-apps)
### Decisões Arquiteturais Registradas (ADRs — links)
### Roadmap Arquitetural (próximas mudanças planejadas)
```

#### 7c. Append line to `registry.jsonl` (audit trail)
```json
{"ts":"ISO8601","event":"XRAY_SCAN","project_slug":"...","data":{"graphify_used":true,"files_scanned":4286,"stack_version":"2026-09-01"}}
```

---

## 3. PÓS-SCAN: 1-PAGE RESUMO DEVOLVIDO AO AGENTE

NÃO encha de linhas no chat. Devolve 10 linhas compactas no final:

```
[harness-xray] ✅ DONE — project_flockr--Lumos (registry: ~/code/harness-sessions/.registry/projects/...)
  ├─ Estrutura: NX-MONOREPO PNPM workspaces · 2 apps · 8 shared packages
  ├─ Stack: TS v5 + Next.js 16 (RSC) · TypeORM v0.3 · Postgres · Redis · Stripe
  ├─ Arquitetura: Router→Service→Repository SIM (detectado 14 routers)
  ├─ Testes: Vitest + Playwright · 0 arquivos unitários / 14 specs E2E
  ├─ Data layer: @flockr/db packages · 38 migrations · RLS Supabase
  ├─ Auth: Auth.js v5 + cookie JWT session
  ├─ CI/CD: GitHub Actions → Vercel deploy 2 apps
  ├─ ⚠️  2 RED FLAGS: (1) @flockr/db god package 2.3k arquivos (2) sem tests unitários
  ├─ Knowledge graph: graphify v0.9.53 OK (4286 arquivos indexados)
  └─ ── Next step: agora rode /harness-project-knowledge para preencher produto, roadmap, arquitetura manual
```

---

## 4. IDEMPOTÊNCIA + REFRESH

Quando rerun `/harness-xray`:
1. Lê o `project_profile.md` existente, mergeia novos findings NÃO destrói seção human-edited (marcadas "Manual Part")
2. A seção "⚙️ Auto-populated" sempre sobrescreve (elas são geradas)
3. Seções "🧭 Manual Part" NUNCA são tocadas (só são criadas na 1ª vez)
4. Dá diff do que mudou desde último scan: `2 novas packages adicionadas, 1 framework versão upgrade: Next 15→16`
5. Sempre append 1 linha nova em `registry.jsonl` com diff resumido.
