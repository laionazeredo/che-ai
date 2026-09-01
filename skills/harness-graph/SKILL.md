---
name: "harness-graph"
description: "Wrapper canônico e genérico do Graphify CLI (pipx package graphifyy = tree-sitter AST knowledge graph 100% local, 33 linguagens). Subcomandos: refresh, query 'pergunta', path A B, stats. Produz graphify-out/ na raiz do worktree (gitignored). Suporta fallback leve (grep-based) se graphify não instalado. Integração com harness-xray (auto refresh durante onboarding)."
---

# Harness Graph — Knowledge Graph AST (Graphify CLI Wrapper)

> **Canonical tool:** Graphify CLI (PyPI: `graphifyy`, double `y`)
> **Instalar:** `pipx install graphifyy`
> **Version tested:** 0.9.x+
> **Onde gera output:** `$WORKTREE_ROOT/graphify-out/` (sempre gitignored global, commitar nunca)

## 0. QUANDO USAR

| Subcomando | Quando | Exemplo |
|---|---|---|
| `refresh` | (1) 1ª vez no repo · (2) depois de pull grande · (3) antes de `/harness-xray` | `/harness-graph refresh` |
| `query "pergunta"` | Perguntas em linguagem natural sobre ESTRUTURA do código | `/harness-graph query "onde ficam as tabelas de refund e qual service valida o valor maximo de reembolso?"` |
| `path "A" "B"` | Busca caminho de dependência/calls entre 2 símbolos ou arquivos | `/harness-graph path "RefundService.processRefund" "Stripe.refunds.create"` |
| `stats` | Snapshot conhecimento: arquivos indexados, top linguagens, hubs de importação | `/harness-graph stats` |

---

## 1. PRÉ-REQUISITO CLI + FALLBACK

```bash
# Check rápido
if command -v graphify >/dev/null 2>&1; then
  GRAPH_ENGINE="graphify"
  GRAPHIFY_V="$(graphify --version 2>/dev/null || echo unknown)"
else
  echo "[harness-graph] ⚠️  graphify CLI NÃO encontrado."
  echo "  Instalar (1 comando, ~30s): pipx install graphifyy"
  echo "  Prosseguindo com FALLBACK LEVE baseado em Grep (menor precisão, sem graph knowledge)."
  GRAPH_ENGINE="grep-fallback"
fi
```

**Regra de blast radius:** NÃO instalar `graphifyy` automaticamente dentro do skill. Promptar o usuário para rodar `pipx install graphifyy` manualmente. (Segurança + não instalar pacotes de sistema sem OK.)

---

## 2. SUBCOMANDOS

### 2.1 `refresh` (atualiza graphify-out/)

Execução canônica:
```bash
cd "$WORKTREE_ROOT"

# Se é a 1ª vez (não existe graphify-out/GRAPH_REPORT.md) → full scan
# Senão → incremental scan (só arquivos modificados desde último ts)

if [ "$GRAPH_ENGINE" = "graphify" ]; then
  if [ -f graphify-out/GRAPH_REPORT.md ]; then
    # Incremental (mais rápido ~50%)
    graphify . --update 2>&1 | tail -n 5
  else
    # Primeira vez
    graphify . 2>&1 | tail -n 5
  fi
  RESULT=$?
else
  # Fallback: estrutura de pastas + extensões top-N (não gera arquivo, só imprime resumo)
  echo "[harness-graph refresh] fallback grep-based scan:"
  find "$WORKTREE_ROOT" -maxdepth 3 -type d -not -path '*/node_modules*' -not -path '*/.git*' -not -path '*/.next*' | head -40
  find "$WORKTREE_ROOT" -type f -not -path '*/node_modules*' -not -path '*/.git*' \
    | sed -E 's/.*\.([a-z]+)$/\1/' | sort | uniq -c | sort -rn | head -10
  RESULT=0
fi

# Audit trail (sempre append registry.jsonl se existir)
if [ -n "${HARNESS_PROJECT_REGISTRY:-}" ] && [ -f "$HARNESS_PROJECT_REGISTRY" ]; then
  echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"GRAPH_REFRESH\",\"project_slug\":\"${HARNESS_PROJECT_SLUG:-unknown}\",\"data\":{\"engine\":\"$GRAPH_ENGINE\",\"version\":\"${GRAPHIFY_V:-n/a}\",\"ok\":$RESULT}}" \
    >> "$HARNESS_PROJECT_REGISTRY"
fi

[ $RESULT -eq 0 ] || { echo "[harness-graph refresh] ❌ falhou. Verifique graphify --version." >&2; exit 1; }
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

## 3. .gitignore OBRIGATÓRIO NO WORKTREE

`graphify-out/` **NUNCA vai para PR / commit.**

Se o worktree não tiver `.gitignore` com graphify-out, este skill adiciona NO FINAL do `.gitignore` do worktree 1 linha:
```
graphify-out/
```
**Regra hard:** NÃO adiciona essa linha se `.gitignore` já tem ela (idempotente). Usa grep para checar antes.

---

## 4. INTEGRAÇÕES DO ECOSSISTEMA HARNESS

Que skills usam harness-graph:
1. **harness-xray (onboarding)** — chama `/harness-graph refresh` como Passo 1 do pipeline de scan; absorve `stats` + top hubs no `project_profile.md`.
2. **harness-scope-checker (CHECK 5 LEAN)** — `/harness-graph query "quais módulos são usados nesta implementação? quais não precisam ser importados?"` para detectar imports sobreabundantes (acoplamento alto = Lean finding).
3. **harness-code-review (before code)** — Se diff introduz novo package ≥3 arquivos → `/harness-graph path "router.handler" "new.Package.method"` para checar se há information leakage (Ousterhout Appendix D = HIGH finding).
4. **harness-fix (scientific debugging)** — Bug em ponto X? `path "entrada API" "ponto X"` = identificação do caminho completo = reduz hypotheses desnecessárias.
5. **harness-spec (antes de especificar)** — query "como já fazemos X hoje no código?" → spec não propõe reimplementar o que já existe (KISS/YAGNI).

---

## 5. VERSIONAMENTO + ROLLBACK

- **graphify CLI versões:** pin para >= 0.9.x se instalar via pipx. Ousterhout + Graph knowledge graph versão API pode mudar em 1.0.
- **Rollback:** Se graphify der crash em algum projeto, é só desinstalar → harness-graph cai automaticamente no fallback grep-based. Nada quebra. Reversível.
- **Cache:** `graphify-out/` pode ser apagado a qualquer momento (`rm -rf graphify-out/`). Próximo `refresh` recria do zero sem side effects.
