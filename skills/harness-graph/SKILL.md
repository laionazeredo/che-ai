---
name: "harness-graph"
description: "Wrapper canônico e genérico do Graphify CLI (pipx package graphifyy = tree-sitter AST knowledge graph 100% local, 33 linguagens). Subcomandos: refresh, query 'pergunta', path A B, stats. Output cache FICA FORA WORKTREE em $HARNESS_WORKSPACE_SHARED/graphify/<related_id>/. Suporta fallback chain de engines Node.js alternativos (CodeGraph npm, @sentropic/graphify, codebase-vis, @lubab/madar) e fallback final leve grep-based se nenhum instalado. Integração com harness-xray (auto refresh durante onboarding). NÃO cria artefatos NEM edita .gitignore na worktree do usuário."
---

# Harness Graph — Knowledge Graph AST (Engine Wrapper com fallback chain)

> **Canonical default tool:** Graphify CLI (PyPI: `graphifyy`, double `y`)
> **Instalar (RECOMENDADO default):** `pipx install graphifyy`
> **Version tested:** 0.9.x+
> **Onde gera output:** `$HARNESS_WORKSPACE_SHARED/graphify/<related_id>/` (FORA worktree do usuário; nunca commita; não precisa de .gitignore)

---

## -0.1 STORAGE BOUNDARY PREFLIGHT (OBRIGATÓRIO ANTES DE TUDO)

```bash
# 1. Carrega contrato de sessões
source ~/.trae/contracts/harness_sessions_contract.sh

# 2. Resolve WORKTREE_ROOT + SESSION_ID
WORKTREE_ROOT="${WORKTREE_ROOT:-$(pwd)}"
SESSION_ID="${SESSION_ID:-graph-standalone-$(date -u +%Y%m%d-%H%M%S)}"

# 3. Calcula paths canônicos + assegura dirs
harness_compute_paths "$WORKTREE_ROOT" "$SESSION_ID" "$PWD"
harness_ensure_session_dirs "$WORKTREE_ROOT"

# 4. Double-guard: outputs NUNCA dentro worktree
harness_assert_outside_worktree "$HARNESS_SESSION_DIR" "$WORKTREE_ROOT" "HARNESS_SESSION_DIR"
harness_assert_outside_worktree "$HARNESS_WORKSPACE_SHARED" "$WORKTREE_ROOT" "HARNESS_WORKSPACE_SHARED"

# 5. Constrói UMA VEZ paths de output do graph (todos FORA worktree)
WORKTREE_SLUG_CANONICAL="$(basename "$WORKTREE_ROOT" | sed 's/[^A-Za-z0-9._-]/-/g' | tr '[:upper:]' '[:lower:]')"
GRAPHIFY_RELATED_ID="${GRAPHIFY_RELATED_ID:-graphify-${WORKTREE_SLUG_CANONICAL}}"

# Truque: gerar um filename dummy via helper, dirname() nos dá a subpasta canônica
GRAPHIFY_OUTPUT_ROOT="$(dirname -- "$(harness_output_path "graphify" ".keep" "${GRAPHIFY_RELATED_ID}" "workspace" "md")")"
harness_assert_outside_worktree "$GRAPHIFY_OUTPUT_ROOT" "$WORKTREE_ROOT" "GRAPHIFY_OUTPUT_ROOT"
mkdir -p "$GRAPHIFY_OUTPUT_ROOT"

GRAPH_REPORT_PATH="${GRAPHIFY_OUTPUT_ROOT}/GRAPH_REPORT.md"
```

**NÃO INVENTE:** Nenhum outro caminho nesta skill. Todo cache, index, artefato do graphify fica ABAIXO de `$GRAPHIFY_OUTPUT_ROOT`. Se for necessário outros subfiles (graph.db, index.sqlite, nodes.json) → `$GRAPHIFY_OUTPUT_ROOT/<nome>`. `harness_cleanup_legacy_artifacts_in_worktree` já remove `graphify-out/` se caiu por engano em worktree antiga.

> **Alternativas 100% Node.js (OPCIONAL · unificar ecossistema só JS):**
> O harness usa a primeira engine encontrada nesta ordem (fallback chain declarativa):
> 1. `codegraph` CLI — `npm install -g @colbymchenry/codegraph` (21 linguagens · MCP · SQLite FTS5 · file watcher incremental · ~58% fewer tool calls benchmarks)
> 2. `graphify` (@sentropic) CLI — `npm install -g @sentropic/graphify` (multimodal código+PDFs+CSVs+ontologia)
> 3. `codebase-vis` CLI — `npm install -g codebase-vis` (só depgraph, 6 linguagens, 17 deps, mais leve)
> 4. `madar` CLI — `npm install -g @lubab/madar` (TS/Node context-pack compiler, 5.28× fewer tokens)
> 5. `graphify` Python default acima
> 6. **Fallback final:** grep-based (sem ferramenta nenhuma instalada, menor precisão)
>
> Comparativo completo + comandos install:
> → [README.md §Getting Started 3b](file:///home/laion/.trae/README.md#L38-L55)

## 0. QUANDO USAR

| Subcomando | Quando | Exemplo |
|---|---|---|
| `refresh` | (1) 1ª vez no repo · (2) depois de pull grande · (3) antes de `/harness-xray` | `/harness-graph refresh` |
| `query "pergunta"` | Perguntas em linguagem natural sobre ESTRUTURA do código | `/harness-graph query "onde ficam as tabelas de refund e qual service valida o valor maximo de reembolso?"` |
| `path "A" "B"` | Busca caminho de dependência/calls entre 2 símbolos ou arquivos | `/harness-graph path "RefundService.processRefund" "Stripe.refunds.create"` |
| `stats` | Snapshot conhecimento: arquivos indexados, top linguagens, hubs de importação | `/harness-graph stats` |

---

## 1. PRÉ-REQUISITO CLI + FALLBACK CHAIN (6 engines)

```bash
# Fallback chain declarativa: codegraph → @sentropic/graphify → codebase-vis → madar → graphify python → grep-fallback
unset GRAPH_ENGINE; unset GRAPH_ENGINE_V
for candidate in "codegraph:codegraph" "graphify:@sentropic" "codebase-vis:codebasevis" "madar:madar" "graphify:graphifyy"; do
  bin="${candidate%%:*}"
  label="${candidate##*:}"
  if command -v "$bin" >/dev/null 2>&1; then
    GRAPH_ENGINE="$label"
    GRAPH_ENGINE_V="$("$bin" --version 2>/dev/null || echo unknown)"
    break
  fi
done
if [ -z "${GRAPH_ENGINE:-}" ]; then
  echo "[harness-graph] ⚠️  Nenhuma engine de graph knowledge instalada."
  echo "  Escolha UMA (1 comando cada, ~30s):"
  echo "    · (Default RECOMENDADO) pipx install graphifyy       (Python · 33+ linguagens · multimodal | gráfico canônico graph.html)"
  echo "    · (Node 1ª escolha)  npm i -g @colbymchenry/codegraph (Node · 21 linguagens · MCP + FTS5 · auto-sync incremental)"
  echo "    · Ver lista completa no README.md §Getting Started 3b."
  echo "  Prosseguindo com FALLBACK FINAL baseado em Grep (menor precisão, sem graph knowledge)."
  GRAPH_ENGINE="grep-fallback"
fi
echo "[harness-graph] Engine selecionada: $GRAPH_ENGINE v${GRAPH_ENGINE_V:-}"
```

**Regra de blast radius:** NÃO instalar automaticamente NENHUMA engine dentro do skill. Promptar o usuário para rodar UM comando de instalação de sua escolha manualmente. (Segurança + não instalar pacotes de sistema sem OK.)

---

## 2. SUBCOMANDOS

### 2.1 `refresh` (atualiza knowledge graph cache)

Execução canônica. **TODOS outputs ficam em `$GRAPHIFY_OUTPUT_ROOT` FORA worktree. NÃO usamos `graphify-out/` padrão dentro worktree.**

```bash
# Garantimos diretório de output FORA worktree (já criado no PREFLIGHT)
[ -n "${GRAPHIFY_OUTPUT_ROOT:-}" ] || { echo "[harness-graph refresh] ❌ PREFLIGHT NÃO rodou. GRAPHIFY_OUTPUT_ROOT vazio." >&2; exit 99; }
harness_assert_outside_worktree "$GRAPHIFY_OUTPUT_ROOT" "$WORKTREE_ROOT" "GRAPHIFY_OUTPUT_ROOT"

if [ "$GRAPH_ENGINE" = "graphify" ]; then
  if [ -f "$GRAPH_REPORT_PATH" ]; then
    # Incremental (mais rápido ~50%). --output-dir garante cache FORA worktree.
    graphify "$WORKTREE_ROOT" --update --output-dir "$GRAPHIFY_OUTPUT_ROOT" 2>&1 | tail -n 5
  else
    # Primeira vez. --output-dir garante cache FORA worktree, NÃO gera nada dentro $WORKTREE_ROOT.
    graphify "$WORKTREE_ROOT" --output-dir "$GRAPHIFY_OUTPUT_ROOT" 2>&1 | tail -n 5
  fi
  RESULT=$?
elif [ "$GRAPH_ENGINE" = "codegraph" ] || [ "$GRAPH_ENGINE" = "codebasevis" ] || [ "$GRAPH_ENGINE" = "madar" ] || [ "$GRAPH_ENGINE" = "@sentropic/graphify" ]; then
  # Fallback engines Node.js: sempre passe output-dir fora worktree.
  # Se engine não suportar --output-dir, CD para $GRAPHIFY_OUTPUT_ROOT e rode de lá apontando para $WORKTREE_ROOT
  ( cd "$GRAPHIFY_OUTPUT_ROOT" && "${GRAPH_ENGINE%%:*}" scan "$WORKTREE_ROOT" 2>&1 | tail -n 5 )
  RESULT=$?
else
  # Fallback final: estrutura de pastas + extensões top-N (não gera arquivo, só imprime resumo)
  echo "[harness-graph refresh] fallback grep-based scan:"
  find "$WORKTREE_ROOT" -maxdepth 3 -type d -not -path '*/node_modules*' -not -path '*/.git*' -not -path '*/.next*' | head -40
  find "$WORKTREE_ROOT" -type f -not -path '*/node_modules*' -not -path '*/.git*' \
    | sed -E 's/.*\.([a-z]+)$/\1/' | sort | uniq -c | sort -rn | head -10
  RESULT=0
fi

# Audit trail (sempre append decision log FORA worktree — usando helper oficial)
harness_append_decision_jsonl "GRAPH_REFRESH" "{\"related_id\":\"${GRAPHIFY_RELATED_ID}\",\"engine\":\"${GRAPH_ENGINE}\",\"version\":\"${GRAPHIFY_V:-n/a}\",\"ok\":${RESULT},\"output_root\":\"${GRAPHIFY_OUTPUT_ROOT}\"}"

[ $RESULT -eq 0 ] || { echo "[harness-graph refresh] ❌ falhou. Verifique graphify --version." >&2; exit 1; }

# NÃO editamos .gitignore do usuário. Como cache está FORA worktree, nunca aparece em git status.
```

### 2.2 `query "<pergunta>"` (pergunta NL)

Resposta enxuta (máximo 20 linhas no output chat). Prioriza:
1. Resposta do graphify CLI se disponível
2. Fallback: smart grep com regex derivado da pergunta + file-type filter

Exemplos consultas úteis reais:
```bash
/harness-graph query "qual é o entry point do Next.js app e onde é configurado o tRPC createCallerFactory?"
/harness-graph query "lista todos os TypeORM Entity classes e seus arquivos"
/harness-graph query "onde são definidos os middlewares de auth (proteção de rota) e como são aplicados nas routers?"
/harness-graph query "existe alguma validação de valor maximo de reembolso? onde fica?"
```

Regra: **SEMPRE retorna paths absolutos canônicos com ranges de linha** (ex: `packages/db/src/entities/RefundRequest.ts#L12-L34`) para que agente pule direto pro código usando Read.

### 2.3 `path "simbA" "simbB"` (dependency path)

Retorna cadeia de chamadas / importações de A → B em **ORDEM DIRETA**.

Exemplo:
```bash
/harness-graph path "RefundRouter.processRefund POST handler" "Stripe.Refunds API call"
# Output esperado:
# RefundRouter (L52) → RefundService.process() (L203) → RefundValidator.assertWithinLimits() (L81)
#                 → StripeClient.refundCreate() (L44 packages/stripe/src/client.ts)
```

Fallback leve (graphify sem path): analisa import chain manual via `grep -R "from .*" import { A }` acíclico BFS.

### 2.4 `stats` (10 linhas snapshot)

Sempre formato estável (scripts parseiam):
```
[harness-graph stats] <repo-slug> @ <ISO ts UTC>
  engine: graphify v0.9.53
  files_scanned_total: 4,286  (excluded 18,302 = node_modules/.git/.next)
  languages:
    TypeScript .ts + .tsx = 83.2%   (3,566)
    SQL migrations .sql = 6.1%      (261)
    Shell .sh = 3.9%                (167)
    CSS .css = 2.8%                 (120)
    Markdown .md = 4.0%             (172)
  import_hubs_top5 (mais importados):
    1. @flockr/db/src/index.ts        (referenciado 142x)
    2. @flockr/trpc/src/client.ts     (89x)
    3. packages/platform/src/lib/stripe.ts (67x)
    4. @flockr/ui/src/button.tsx      (55x)
    5. packages/platform/src/app/api/trpc/route.ts (41x)
  knowledge_graph_age: 1h 17m  (último refresh: 2026-09-01 18:05 UTC)
```

---

## 3. INTEGRAÇÕES DO ECOSSISTEMA HARNESS

Que skills usam harness-graph:
1. **harness-xray (onboarding)** — chama `/harness-graph refresh` como Passo 1 do pipeline de scan; absorve `stats` + top hubs no `project_profile.md`.
2. **harness-scope-checker (CHECK 5 LEAN)** — `/harness-graph query "quais módulos são usados nesta implementação? quais não precisam ser importados?"` para detectar imports sobreabundantes (acoplamento alto = Lean finding).
3. **harness-code-review (before code)** — Se diff introduz novo package ≥3 arquivos → `/harness-graph path "router.handler" "new.Package.method"` para checar se há information leakage (Ousterhout Appendix D = HIGH finding).
4. **harness-fix (scientific debugging)** — Bug em ponto X? `path "entrada API" "ponto X"` = identificação do caminho completo = reduz hypotheses desnecessárias.
5. **harness-spec (antes de especificar)** — query "como já fazemos X hoje no código?" → spec não propõe reimplementar o que já existe (KISS/YAGNI).

---

## 4. VERSIONAMENTO + ROLLBACK

- **graphify CLI versões:** pin para >= 0.9.x se instalar via pipx. Ousterhout + Graph knowledge graph versão API pode mudar em 1.0.
- **Rollback:** Se graphify der crash em algum projeto, é só desinstalar → harness-graph cai automaticamente no fallback grep-based. Nada quebra. Reversível.
- **Cache (TODOS FORA WORKTREE):** `$GRAPHIFY_OUTPUT_ROOT` pode ser apagado a qualquer momento (`rm -rf "$GRAPHIFY_OUTPUT_ROOT"`). Próximo `refresh` recria do zero sem side effects.
- **Legacy cleanup:** `harness_cleanup_legacy_artifacts_in_worktree` já move `graphify-out/` antigo (caiu dentro worktree por bug) para backup seguro em `$HARNESS_WORKSPACE_SHARED/legacy_cleanup/`.
