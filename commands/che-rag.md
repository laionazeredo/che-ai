---
description: "RAG (Retrieval Augmented Generation) search with hybrid BM25 lexical + vector embeddings. Builds incremental index from project durable docs (architecture, specs, envelopes, decisions). sqlite-vec optional, zero-deps fallback always works."
arguments:
  - name: action
    description: "build-index | search. build-index = updates incremental index. search = hybrid query."
    required: true
  - name: worktree
    description: "Absolute worktree path. If session BOUND binding exists, uses WORKTREE_ROOT default."
    required: false
  - name: query_text
    description: "Only for action=search. Semantic search query in Portuguese or English. Wrap in quotes."
    required: false
  - name: provider
    description: "Only for action=build-index. auto | none | sentence-transformers | openai. Default = auto (always falls back to none if nothing available)."
    required: false
  - name: top_k
    description: "Only for action=search. Default = 10. Number of hybrid results."
    required: false
  - name: no-hybrid
    description: "Only for action=search. Flag without value: if passed, runs only BM25 lexical without vector."
    required: false
---

# `/che-rag` — Retrieval Augmented Generation

Offers two actions:

**A) `build-index`**: Incrementally builds/refreshes the RAG index from canonical sources of truth:
- L2 Project Durable: `project_profile.md`, `architecture.md`, `product_context.md`, `roadmap.md`.
- L3 Worktree Shared: `specs/*.md` (all Approved/Draft specs), `tasks/*/envelope.md` (envelopes), `decisions.log.jsonl` (50-line blocks), `task_graph.md`.

Chunking: 512 tokens ≈ 384 words with 10% overlap. SHA-256 hash per chunk (path + id + text) → unchanged chunks are SKIPPED.

Supported providers:
- `auto` (recommended) → tries sentence-transformers → OPENAI_API_KEY → always falls back to `none` (no crash).
- `none` → ZERO DEPENDENCIES fallback: dummy vectors, vector scores = constant → 100% BM25. Always works.
- `openai` / `sentence-transformers` → requires library and key installed/set; if missing, falls back to `none` + warning in return.

sqlite-vec is **optional**: if the extension cannot load (restricted environment), build and search still work via lexical only.

**B) `search`**: Weighted **hybrid search (40% BM25 lexical + 60% cosine vector)**. Each score is normalized [0,1] before merging. Results ordered by `hybrid_score`.

---

## Pre-flight per action

### Action `build-index`
1. Resolve WORKTREE_ROOT.
2. DOES NOT need state store. Runs standalone.
3. Execute:
   ```bash
   python3 -m che_core.cli rag build-index "$WORKTREE_ROOT" \
     --chunk-size 512 \
     --provider auto
   ```
4. Report to user: `chunks_total`, `inserted` (new), `skipped_cached` (unchanged), `deleted_stale` (removed), `sqlite_vec_loaded` (bool), actual `provider` used.

### Action `search`
1. Resolve WORKTREE_ROOT.
2. If `che_rag.sqlite` DB does not exist OR was created more than 7 days ago OR is newer than `decisions.log` mtime → execute `build-index` SILENTLY first (do not ask user).
3. Execute:
   ```bash
   python3 -m che_core.cli rag search "$WORKTREE_ROOT" "$QUERY_TEXT" \
     --top-k 10 \
     --hybrid
   ```
4. Display top-k ordered by `hybrid_score`, showing `scope` + `source_path` (with #Lx-Ly if applicable) + 2-line `text_body` snippet.

---

## Examples

```
/che-rag action=build-index worktree=/home/laion/code/flockr/Lumos provider=auto
/che-rag action=search  worktree=/home/laion/code/flockr/Lumos "Which decisions about RLS in the events database?" top_k=8
/che-rag action=search "refund flow in Stripe" no-hybrid
```
