import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from che_core.paths import compute_paths

RAG_DB_FILENAME = "che_rag.sqlite"


# ---------------------------------------------------------------------------
# Providers abstratos + implementações (zero-deps mandatory default)
# ---------------------------------------------------------------------------


class EncodeProvider:
    """Abstract encoder. Toda implementação deve garantir encode() sempre retorna list[list[float]] mesmo em fallback."""

    name: str = "abstract"

    def encode(self, texts: List[str]) -> List[List[float]]:  # pragma: no cover - abstract
        raise NotImplementedError


class NoneBM25Provider(EncodeProvider):
    """Fallback ZERO DEPENDÊNCIAS: retorna vetores dummy unitários de dimensão 8.
    Com isso sqlite-vec carrega, scores vetoriais = cosseno similar entre unitários = constante;
    search_rag híbrido cai automaticamente para 100% BM25 lexical, sem crash.
    Funciona SEM pip install nenhum."""

    name = "none"

    def __init__(self, dim: int = 8):
        self.dim = dim
        self._vec = [1.0 / (dim**0.5)] * dim

    def encode(self, texts: List[str]) -> List[List[float]]:
        return [list(self._vec) for _ in texts]


class _SentenceTransformersProvider(EncodeProvider):
    name = "sentence-transformers"

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", dim: int = 384):
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as e:  # pragma: no cover - só cai se AutoProvider chutar errado
            raise RuntimeError("sentence-transformers not installed") from e
        self._model = SentenceTransformer(model_name)
        self.dim = dim

    def encode(self, texts: List[str]) -> List[List[float]]:
        arr = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return [row.astype(float).tolist() for row in arr]


class OpenAIProvider(EncodeProvider):
    """Requer OPENAI_API_KEY + lib openai instalada (opcional). Se falhar => raise RuntimeError para AutoProvider."""

    name = "openai"

    def __init__(self, model: str = "text-embedding-3-small", dim: int = 1536):
        import os

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:
            raise RuntimeError("openai lib not installed") from e
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self.dim = dim

    def encode(self, texts: List[str]) -> List[List[float]]:
        batch_size = 100
        out: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            resp = self._client.embeddings.create(input=chunk, model=self._model)
            out.extend([e.embedding for e in resp.data])
        return out


class AnthropicProvider(EncodeProvider):
    """Anthropic não tem endpoint de embeddings público em 2024-01. Implementação de contrato forward-compatible:
    usa Voyage AI opcional ou fallback; por segurança, se ANTHROPIC_API_KEY existir mas sem modelo embedding,
    cai em RuntimeError para AutoProvider escolher None."""

    name = "anthropic"

    def __init__(self):
        import os

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        raise RuntimeError("Anthropic embedding endpoint not available; please use --provider=none or openai")

    def encode(self, texts: List[str]) -> List[List[float]]:  # pragma: no cover - __init__ já raise
        raise RuntimeError("not available")


def _auto_provider() -> Tuple[EncodeProvider, str]:
    """Tenta, na ordem: (1) sentence-transformers instalado, (2) OPENAI_API_KEY setada + lib,
    (3) ANTHROPIC_API_KEY (falhará), (4) SEMPRE cai em NoneBM25Provider no final.
    Nunca retorna erro — sempre há um provider funcional."""
    try:
        p = _SentenceTransformersProvider()
        return p, p.name
    except Exception:
        pass
    try:
        p = OpenAIProvider()
        return p, p.name
    except Exception:
        pass
    try:
        AnthropicProvider()
    except Exception:
        pass
    p = NoneBM25Provider()
    return p, p.name + "-bm25-fallback"


def get_provider(name: str) -> Tuple[EncodeProvider, str, int]:
    """Retorna (provider instance, label usada no metadata, embedding dim)."""
    n = (name or "auto").lower().strip()
    if n == "auto":
        p, label = _auto_provider()
        return p, label, getattr(p, "dim", 8)
    if n in ("none", "bm25", ""):
        p = NoneBM25Provider()
        return p, "none", p.dim
    if n in ("st", "sentence-transformers", "sentence_transformers"):
        p = _SentenceTransformersProvider()
        return p, p.name, p.dim
    if n == "openai":
        p = OpenAIProvider()
        return p, p.name, p.dim
    if n == "anthropic":
        p = AnthropicProvider()
        return p, p.name, getattr(p, "dim", 0)
    # desconhecido => fallback none, warning no metadata
    p = NoneBM25Provider()
    return p, f"none(unknown:{n})", p.dim


# ---------------------------------------------------------------------------
# Chunker (zero-dep, aproximado 0.75 words-per-token ratio)
# ---------------------------------------------------------------------------


def _split_md_chunks(text: str, source_path: str, chunk_words: int) -> List[Dict[str, Any]]:
    """Chunk por ~chunk_words palavras com 10% overlap. Preserva títulos markdown como heuristic anchor.
    Sem lib tokenizer: words ≈ 0.75 * tokens. Para 512 tokens → ≈ 384 words."""
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[Dict[str, Any]] = []
    current_words: List[str] = []
    current_len = 0
    chunk_id = 0
    overlap_window: List[str] = []
    overlap_size = max(10, chunk_words // 10)

    def _flush():
        nonlocal current_words, current_len, chunk_id, overlap_window
        if not current_words:
            return
        body = " ".join(current_words)
        chunks.append(
            {
                "source_path": source_path,
                "chunk_id": chunk_id,
                "text_body": body,
                "word_count": len(current_words),
            }
        )
        overlap_window = current_words[-overlap_size:] if len(current_words) >= overlap_size else current_words
        chunk_id += 1
        current_words = list(overlap_window)
        current_len = len(current_words)

    for para in paragraphs:
        w = para.split()
        # Se um único parágrafo > chunk_words, quebra frases internas também
        if len(w) > chunk_words:
            sentence_parts = re.split(r"(?<=[.!?])\s+", para)
            buf: List[str] = []
            for sp in sentence_parts:
                sp_w = sp.split()
                if len(buf) + len(sp_w) > chunk_words and buf:
                    current_words.extend(buf)
                    current_len += len(buf)
                    _flush()
                    buf = []
                buf.extend(sp_w)
            if buf:
                current_words.extend(buf)
                current_len += len(buf)
        else:
            if current_len + len(w) > chunk_words:
                _flush()
            current_words.extend(w)
            current_len += len(w)
    if current_words:
        _flush()
    return chunks


def _collect_doc_sources(paths: Dict[str, str]) -> List[Tuple[str, str, str]]:
    """Varre L2 (project dir) + L3 worktree shared em busca de fontes de texto para indexar.
    Retorna [(scope, source_path, file_content)].
    Scope ∈ {project_profile, architecture, product_context, roadmap, spec, task_envelope, decision}."""
    project_dir = Path(paths["CHE_PROJECT_DIR"])
    ws_shared = Path(paths["CHE_WORKSPACE_SHARED"])

    out: List[Tuple[str, str, str]] = []

    # --- L2 PROJECT DURABLE ---
    for name, scope in [
        ("project_profile.md", "project_profile"),
        ("architecture.md", "architecture"),
        ("product_context.md", "product_context"),
        ("roadmap.md", "roadmap"),
    ]:
        p = project_dir / name
        if p.is_file():
            try:
                out.append((scope, str(p), p.read_text(encoding="utf-8")))
            except Exception:
                pass

    # --- L3 SPECS ---
    specs_dir = ws_shared / "specs"
    if specs_dir.is_dir():
        for p in sorted(specs_dir.rglob("*.md")):
            try:
                out.append(("spec", str(p), p.read_text(encoding="utf-8")))
            except Exception:
                pass

    # --- L3 TASK ENVELOPES ---
    tasks_dir = ws_shared / "tasks"
    if tasks_dir.is_dir():
        for p in sorted(tasks_dir.rglob("envelope.md")):
            try:
                out.append(("task_envelope", str(p), p.read_text(encoding="utf-8")))
            except Exception:
                pass

    # --- L3 DECISIONS LOG (como chunks line-range) ---
    dec_path = ws_shared / "decisions.log.jsonl"
    if dec_path.is_file():
        try:
            lines = dec_path.read_text(encoding="utf-8").splitlines()
            # 1 chunk por bloco de 50 decisions
            block_size = 50
            for i in range(0, len(lines), block_size):
                block = "\n".join(lines[i : i + block_size])
                out.append(("decision", f"{dec_path}#L{i + 1}-L{min(i + block_size, len(lines))}", block))
        except Exception:
            pass

    # --- L3 TASK_GRAPH.md ---
    tg = ws_shared / "task_graph.md"
    if tg.is_file():
        try:
            out.append(("task_graph", str(tg), tg.read_text(encoding="utf-8")))
        except Exception:
            pass

    return out


# ---------------------------------------------------------------------------
# RAGStore SQLite + sqlite-vec OPCIONAL
# ---------------------------------------------------------------------------


def _get_rag_db_path(worktree_root: Optional[str] = None, paths: Optional[Dict[str, str]] = None) -> Path:
    if paths is None:
        if worktree_root is None:
            raise ValueError("worktree_root or paths must be provided")
        paths = compute_paths(worktree_root, "rag-store-fallback")
    return Path(paths["CHE_PROJECT_DIR"]) / RAG_DB_FILENAME


def _try_load_sqlite_vec(conn: sqlite3.Connection) -> Tuple[bool, Optional[str]]:
    """Tenta carregar sqlite-vec. Retorna (loaded_ok, error_message). NUNCA dá raise."""
    try:
        conn.enable_load_extension(True)
    except Exception as e:
        return False, f"enable_load_extension disabled: {e}"
    try:
        # sqlite-vec distribui módulo Python; tenta caminho .so/.dylib/.dll via importlib
        try:
            import sqlite_vec  # type: ignore

            sqlite_vec.load(conn)
            return True, None
        except Exception as e2:
            # fallback: tenta load por nome genérico
            try:
                conn.load_extension("sqlite3_vec0")
                return True, None
            except Exception:
                pass
            return False, f"sqlite-vec module not loadable: {e2}"
    finally:
        try:
            conn.enable_load_extension(False)
        except Exception:
            pass


def _ensure_rag_schema(conn: sqlite3.Connection, vec_loaded: bool, embedding_dim: int) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS documents (
            hash TEXT PRIMARY KEY,
            scope TEXT NOT NULL DEFAULT '',
            source_path TEXT NOT NULL DEFAULT '',
            chunk_id INTEGER NOT NULL DEFAULT 0,
            text_body TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            UNIQUE(source_path, chunk_id)
        );
        CREATE INDEX IF NOT EXISTS idx_documents_scope ON documents(scope);
        CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source_path);
        """
    )
    # sqlite-vec 0.1.x usa vec0 virtual table; se falhar, apenas skip
    if vec_loaded and embedding_dim and embedding_dim > 0:
        try:
            conn.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_documents USING vec0(embedding float[{embedding_dim}])"
            )
        except Exception:
            pass  # se versão sqlite-vec incompatível, deixa sem vector table


def _hash_chunk(source_path: str, chunk_id: int, text_body: str) -> str:
    h = hashlib.sha256()
    h.update(source_path.encode("utf-8"))
    h.update(b"\x00")
    h.update(str(chunk_id).encode("utf-8"))
    h.update(b"\x00")
    h.update(text_body.encode("utf-8"))
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------


def build_rag_index(
    worktree_root: str,
    chunk_size: int = 512,
    provider: str = "auto",
) -> Dict[str, Any]:
    """Builda ou atualiza incrementalmente o índice RAG.
    Chunks existentes (por source_path+chunk_id) cujo hash não mudou são pulados."""
    enc_prov, prov_label, emb_dim = get_provider(provider)
    chunk_words = max(64, int(chunk_size * 0.75))

    paths = compute_paths(worktree_root, "rag-build-index")
    db_path = _get_rag_db_path(paths=paths)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    vec_loaded, vec_note = _try_load_sqlite_vec(conn)
    if not vec_loaded:
        # se vetor indisponível, força provider none para embeddings dummy consistentes
        if not isinstance(enc_prov, NoneBM25Provider):
            enc_prov = NoneBM25Provider()
            prov_label = prov_label + "+vec-fallback-none"
            emb_dim = enc_prov.dim

    _ensure_rag_schema(conn, vec_loaded, emb_dim)

    # 1. Coleta todos doc sources
    sources = _collect_doc_sources(paths)

    # 2. Split em chunks
    all_chunks: List[Dict[str, Any]] = []
    for scope, src_path, content in sources:
        for ch in _split_md_chunks(content, src_path, chunk_words):
            all_chunks.append(
                {
                    "scope": scope,
                    "source_path": ch["source_path"],
                    "chunk_id": ch["chunk_id"],
                    "text_body": ch["text_body"],
                    "word_count": ch["word_count"],
                }
            )

    # 3. Verifica quais já existem e não mudaram (incremental)
    existing = {
        row["hash"]: (row["source_path"], row["chunk_id"])
        for row in conn.execute("SELECT hash, source_path, chunk_id FROM documents").fetchall()
    }

    to_insert: List[Dict[str, Any]] = []
    for c in all_chunks:
        h = _hash_chunk(c["source_path"], c["chunk_id"], c["text_body"])
        if h in existing:
            continue
        c["hash"] = h
        to_insert.append(c)

    # 4. Embed batch novo + insert
    inserted = 0
    skipped = len(all_chunks) - len(to_insert)
    batch_encode_size = 32
    now_iso = datetime.now(timezone.utc).isoformat()

    for i in range(0, len(to_insert), batch_encode_size):
        batch = to_insert[i : i + batch_encode_size]
        texts = [b["text_body"] for b in batch]
        vecs = enc_prov.encode(texts)
        # Garante dimensão consistente (provider none 8; st 384; openai 1536)
        real_dim = len(vecs[0]) if vecs else emb_dim
        for b, v in zip(batch, vecs):
            cur = conn.cursor()
            try:
                cur.execute(
                    """INSERT INTO documents (hash, scope, source_path, chunk_id, text_body, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(hash) DO NOTHING""",
                    (b["hash"], b["scope"], b["source_path"], b["chunk_id"], b["text_body"], now_iso),
                )
                if cur.rowcount and cur.rowcount > 0:
                    inserted += 1
            except Exception:
                pass
            # vector table insert (se disponível)
            if vec_loaded and real_dim:
                try:
                    import struct

                    blob = struct.pack(f"{real_dim}f", *v)
                    conn.execute(
                        "INSERT OR REPLACE INTO vec_documents(rowid, embedding) VALUES (?, ?)",
                        (b["hash"], blob),
                    )
                except Exception:
                    pass
    conn.commit()

    # 5. Prune documents que não existem mais nas sources (stale)
    valid_keys = {_hash_chunk(c["source_path"], c["chunk_id"], c["text_body"]) for c in all_chunks}
    stale = [h for h in existing if h not in valid_keys]
    deleted = 0
    if stale:
        cur = conn.cursor()
        cur.execute("DELETE FROM documents WHERE hash IN ({})".format(",".join("?" * len(stale))), stale)
        deleted = cur.rowcount or 0
        if vec_loaded:
            try:
                conn.execute("DELETE FROM vec_documents WHERE rowid IN ({})".format(",".join("?" * len(stale))), stale)
            except Exception:
                pass
    conn.commit()
    conn.close()

    return {
        "db_path": str(db_path),
        "provider": prov_label,
        "embedding_dim": emb_dim,
        "sqlite_vec_loaded": vec_loaded,
        "sqlite_vec_note": vec_note,
        "chunks_total": len(all_chunks),
        "skipped_cached": skipped,
        "inserted": inserted,
        "deleted_stale": deleted,
        "sources_count": len(sources),
        "chunk_size_tokens": chunk_size,
        "chunk_words": chunk_words,
    }


# ---------------------------------------------------------------------------
# Search híbrida: BM25 (state_store) 40% + vector cosine 60%
# ---------------------------------------------------------------------------


def _normalize_01(scores: List[float]) -> List[float]:
    if not scores:
        return scores
    mn = min(scores)
    mx = max(scores)
    if mx - mn < 1e-9:
        return [0.5 for _ in scores]
    return [(s - mn) / (mx - mn) for s in scores]


def search_rag(
    worktree_root: str,
    query_text: str,
    top_k: int = 10,
    hybrid: bool = True,
) -> Dict[str, Any]:
    """Busca RAG. Se provider/vetor indisponível ou hybrid=False → só BM25 lexical.
    Strategy: (a) pega top_k*5 lexical via state_store search_state, (b) pega top_k*5 vector via sqlite-vec,
    (c) junta por hash/source_path+chunk_id, (d) weighted merge 0.4 lexical + 0.6 vector."""
    paths = compute_paths(worktree_root, "rag-search")
    db_path = _get_rag_db_path(paths=paths)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    vec_loaded, _vec_note = _try_load_sqlite_vec(conn)

    # --- Passo 1: sempre pega lexical BM25 via state_store (se houver FTS) ou fallback LIKE ---
    lexical_results: List[Dict[str, Any]] = []
    lexical_hits: Dict[str, float] = {}
    try:
        from che_core.state_store import search_state

        sres = search_state(worktree_root, query_text, top_k=max(top_k * 5, 30), scope="all")
        if isinstance(sres, dict):
            items = sres.get("results") or []
            for r in items:
                # r.keys variam por scope; melhor: construir key por source_path se existir, senão por id
                key = r.get("path") or r.get("source_path") or f"lex-{r.get('scope', 'x')}-{r.get('id', '?')}"
                score = float(r.get("score_bm25") or r.get("score") or 0.0)
                lexical_hits[key] = max(lexical_hits.get(key, 0.0), score)
                lexical_results.append({**r, "_join_key": key})
    except Exception:
        pass

    # --- Passo 2: vector search se possível ---
    vector_results: List[Dict[str, Any]] = []
    vector_hits: Dict[str, float] = {}
    if vec_loaded and hybrid:
        # Determina dim real consultando sqlite_vec_info ou a primeira row
        emb_dim = 8
        prov_for_q: Optional[EncodeProvider] = None
        try:
            # detectar dim por metadata ultima build => não existe tabela. Usa heuristica: consulta provider none por enquanto
            row = conn.execute("SELECT COUNT(*) as c FROM documents").fetchone()
            count_doc = row["c"] if row else 0
            if count_doc > 0:
                # tenta carregar vec_documents info
                try:
                    meta = conn.execute("SELECT * FROM vec_documents LIMIT 1").fetchone()
                    if meta and hasattr(meta, "keys"):
                        pass
                except Exception:
                    pass
        except Exception:
            pass
        # para pegar query embedding, reutiliza um provider coerente:
        # se sqlite-vec carregou mas não sabemos dim, usamos none provider (unit vector) que sempre matcha
        # caso contrário, tentamos auto
        if prov_for_q is None:
            prov_for_q, _, emb_dim = get_provider("auto")
        try:
            q_emb = prov_for_q.encode([query_text])[0]
            real_dim = len(q_emb)
            import struct

            blob = struct.pack(f"{real_dim}f", *q_emb)
            rows = conn.execute(
                "SELECT rowid, distance FROM vec_documents WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
                (blob, max(top_k * 5, 30)),
            ).fetchall()
            for r in rows:
                rid = r["rowid"]
                # distance = squared L2 ou cosine dist (menor = melhor). Converter para score similaridade (maior = melhor).
                dist = float(r["distance"])
                sim = 1.0 / (1.0 + dist)
                vector_hits[rid] = sim
                # Join com documents
                drow = conn.execute(
                    "SELECT hash, scope, source_path, chunk_id, text_body FROM documents WHERE hash=?", (rid,)
                ).fetchone()
                if drow:
                    vector_results.append(
                        {
                            "hash": drow["hash"],
                            "scope": drow["scope"],
                            "source_path": drow["source_path"],
                            "chunk_id": drow["chunk_id"],
                            "text_body": drow["text_body"],
                            "score_vector_sim": sim,
                            "score_vector_distance": dist,
                        }
                    )
        except Exception:
            pass

    conn.close()

    # --- Passo 3: merge híbrido ponderado ---
    # Para combinar: lexical score normalizado (40%) + vector score normalizado (60%)
    merged: Dict[str, Dict[str, Any]] = {}

    lex_keys = list(lexical_hits.keys())
    lex_scores_norm = _normalize_01([lexical_hits[k] for k in lex_keys])
    for k, ns in zip(lex_keys, lex_scores_norm):
        merged[k] = {"_join_key": k, "lex_score_norm": ns, "vec_score_norm": 0.0, "count_hits": 1}

    vec_keys = list(vector_hits.keys())
    vec_scores_norm = _normalize_01([vector_hits[k] for k in vec_keys])
    for k, ns in zip(vec_keys, vec_scores_norm):
        if k in merged:
            merged[k]["vec_score_norm"] = max(merged[k]["vec_score_norm"], ns)
            merged[k]["count_hits"] += 1
        else:
            merged[k] = {"_join_key": k, "lex_score_norm": 0.0, "vec_score_norm": ns, "count_hits": 1}

    # Encontrar record base (texto) por cada merged entry
    joined: List[Dict[str, Any]] = []
    for key, m in merged.items():
        # prioriza vector result para texto (mais específico com chunk id)
        rec = next((v for v in vector_results if v.get("hash") == key or v.get("_join_key") == key), None)
        if rec is None:
            rec = next((lr for lr in lexical_results if lr.get("_join_key") == key), None)
        weight_lex = 0.4
        weight_vec = 0.6
        if not vector_hits:
            weight_lex = 1.0
            weight_vec = 0.0
        elif not lexical_hits:
            weight_lex = 0.0
            weight_vec = 1.0
        total_score = m["lex_score_norm"] * weight_lex + m["vec_score_norm"] * weight_vec
        base: Dict[str, Any] = {
            "join_key": key,
            "hybrid_score": round(total_score, 5),
            "lex_score_norm": round(m["lex_score_norm"], 5),
            "vec_score_norm": round(m["vec_score_norm"], 5),
            "hit_count": m["count_hits"],
        }
        if rec:
            base.update({k: v for k, v in rec.items() if not k.startswith("_")})
        joined.append(base)

    joined.sort(key=lambda r: r["hybrid_score"], reverse=True)
    top = joined[:top_k]

    return {
        "query": query_text,
        "top_k_requested": top_k,
        "hybrid": hybrid,
        "sqlite_vec_loaded": vec_loaded,
        "counts": {
            "lexical_matches": len(lexical_hits),
            "vector_matches": len(vector_hits),
            "merged_unique": len(merged),
            "returned": len(top),
        },
        "results": top,
    }
