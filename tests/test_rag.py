"""Smoke test RAG: provider none sempre funciona, build incremental, search não crasha."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

from che_core.paths import ensure_session_dirs
from che_core.rag import NoneBM25Provider, build_rag_index, get_provider, search_rag


def test_none_provider_always_encodes():
    p = NoneBM25Provider(dim=4)
    out = p.encode(["hello world", "segundo texto"])
    assert len(out) == 2
    assert len(out[0]) == 4
    norm = math.sqrt(sum(v * v for v in out[0]))
    assert abs(norm - 1.0) < 1e-6


def test_get_provider_none_returns_none():
    p, label, dim = get_provider("none")
    assert label == "none"
    assert isinstance(p, NoneBM25Provider)
    assert dim == 8


def test_get_provider_unknown_falls_back_to_none():
    p, label, _ = get_provider("nao_existo_xyz")
    assert isinstance(p, NoneBM25Provider)
    assert "none" in label


def _setup_content(tmp_path: Path):
    wt = tmp_path / "wt"
    wt.mkdir()
    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    os.environ["CHE_WORKSPACES_ROOT"] = str(ws_root)
    paths = ensure_session_dirs(str(wt), "rag-smoke")

    (Path(paths["CHE_PROJECT_DIR"]) / "architecture.md").write_text(
        """
# Arquitetura

O sistema usa monorepo NX com aplicações Next.js e pacotes compartilhados: db, auth, trpc, ui.
Camada de dados usa PostgreSQL com RLS habilitado em todas tabelas de tenancy.
Pagamentos processados via Stripe Connect com separacao de fundos entre organizacoes.
""".strip(),
        encoding="utf-8",
    )
    (Path(paths["CHE_PROJECT_DIR"]) / "product_context.md").write_text(
        """
# Produto

Plataforma de ingressos UK-first: descoberta publica, checkout seguro, painel administrativo
para criadores de eventos, e app de scanner para funcionarios na entrada. Moeda GBP.
""".strip(),
        encoding="utf-8",
    )
    specs = Path(paths["CHE_WORKSPACE_SHARED"]) / "specs"
    (specs / "pagamento.md").write_text(
        """---
title: Pagamento
status: Approved
domain: engineering
---

Pagamento usa Stripe Connect. Apos o checkout criamos PaymentIntent por transacao,
e guardamos referencia no banco. Refunds requerem papel admin e registram em log de auditoria.
""".strip(),
        encoding="utf-8",
    )
    return wt


def test_build_rag_index_none_provider_succeeds(tmp_path: Path):
    wt = _setup_content(tmp_path)
    res = build_rag_index(str(wt), chunk_size=64, provider="none")
    assert res["provider"] == "none"
    assert res["chunks_total"] >= 3
    assert res["inserted"] >= 3
    assert Path(res["db_path"]).is_file()
    res2 = build_rag_index(str(wt), chunk_size=64, provider="none")
    assert res2["inserted"] == 0
    assert res2["skipped_cached"] == res["chunks_total"]


def test_search_rag_hybrid_does_not_crash(tmp_path: Path):
    wt = _setup_content(tmp_path)
    build_rag_index(str(wt), chunk_size=64, provider="none")
    # Query de teste. Não garantimos matches pois depende de FTS5; só garantimos serializável e sem crash.
    r = search_rag(str(wt), "Stripe Connect PaymentIntent", top_k=5, hybrid=True)
    assert isinstance(r, dict)
    json.dumps(r)
    assert "results" in r
    assert isinstance(r["results"], list)
    assert "counts" in r
    # counts deve ter lexical_matches (via search_state) sempre >= 0
    assert isinstance(r["counts"]["lexical_matches"], int)
