---
description: "RAG (Retrieval Augmented Generation) search with hybrid BM25 lexical + vector embeddings. Builds incremental index from project durable docs (architecture, specs, envelopes, decisions). sqlite-vec optional, zero-deps fallback always works."
arguments:
  - name: action
    description: "build-index | search. build-index = atualiza índice incremental. search = consulta híbrida."
    required: true
  - name: worktree
    description: "Absolute worktree path. If session BOUND binding exists, uses WORKTREE_ROOT default."
    required: false
  - name: query_text
    description: "Apenas para action=search. Query de busca semântica em português ou inglês. Colocar em aspas."
    required: false
  - name: provider
    description: "Apenas para action=build-index. auto | none | sentence-transformers | openai. Default = auto (sempre cai em none se nada disponível)."
    required: false
  - name: top_k
    description: "Apenas para action=search. Default = 10. Quantidade de resultados híbridos."
    required: false
  - name: no-hybrid
    description: "Apenas para action=search. Flag sem valor: se passado, roda só BM25 lexical sem vetor."
    required: false
---

# `/che-rag` — Retrieval Augmented Generation

Oferece duas ações:

**A) `build-index`**: Constrói/refresca de forma **incremental** o índice RAG a partir das fontes de verdade canônicas:
- L2 Project Durable: `project_profile.md`, `architecture.md`, `product_context.md`, `roadmap.md`.
- L3 Worktree Shared: `specs/*.md` (todos specs Approved/Draft), `tasks/*/envelope.md` (envelopes), `decisions.log.jsonl` (blocos de 50 linhas), `task_graph.md`.

Chunking: 512 tokens ≈ 384 palavras com 10% overlap. Hash SHA-256 por chunk (caminho + id + texto) → chunks inalterados são SKIPADOS.

Providers suportados:
- `auto` (recomendado) → tenta sentence-transformers → OPENAI_API_KEY → sempre cai em `none` (sem crash).
- `none` → fallback ZERO DEPENDÊNCIAS: vetores dummy, scores vetoriais = constante → 100% BM25. Sempre funciona.
- `openai` / `sentence-transformers` → requer lib e chave instalada/setada; se faltar cai `none` + aviso no retorno.

sqlite-vec é **opcional**: se extensão não puder carregar (ambiente restrito), build e search ainda funcionam via lexical only.

**B) `search`**: Busca **híbrida ponderada (40% BM25 lexical + 60% vetor cosseno)**. Cada score é normalizado [0,1] antes do merge. Resultados ordenados por `hybrid_score`.

---

## Pré-flight por ação

### Ação `build-index`
1. Resolve WORKTREE_ROOT.
2. NÃO precisa de state store. Roda standalone.
3. Executa:
   ```bash
   python3 -m che_core.cli rag build-index "$WORKTREE_ROOT" \
     --chunk-size 512 \
     --provider auto
   ```
4. Reporta ao usuário: `chunks_total`, `inserted` (novo), `skipped_cached` (não mudou), `deleted_stale` (removido), `sqlite_vec_loaded` (bool), `provider` real utilizado.

### Ação `search`
1. Resolve WORKTREE_ROOT.
2. Se DB `che_rag.sqlite` não existir OU tiver sido criado há mais de 7 dias ou mais novo que `decisions.log` mtime → executa `build-index` SILENCIOSAMENTE primeiro (não pede user).
3. Executa:
   ```bash
   python3 -m che_core.cli rag search "$WORKTREE_ROOT" "$QUERY_TEXT" \
     --top-k 10 \
     --hybrid
   ```
4. Exibe os top-k ordenados por `hybrid_score`, mostrando `scope` + `source_path` (com #Lx-Ly se existir) + 2 linhas de snippet do `text_body`.

---

## Exemplos

```
/che-rag action=build-index worktree=/home/laion/code/flockr/Lumos provider=auto
/che-rag action=search  worktree=/home/laion/code/flockr/Lumos "Quais decisões sobre RLS no banco de eventos?" top_k=8
/che-rag action=search "refund flow no Stripe" no-hybrid
```
