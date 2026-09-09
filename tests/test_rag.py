"""Smoke test RAG: none provider always works, incremental build, search doesn't crash."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

from che_core.paths import ensure_session_dirs
from che_core.rag import NoneBM25Provider, build_rag_index, get_provider, search_rag


def test_none_provider_always_encodes():
    p = NoneBM25Provider(dim=4)
    out = p.encode(["hello world", "second text"])
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
    p, label, _ = get_provider("non_existent_xyz")
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
# Architecture

The system uses NX monorepo with Next.js applications and shared packages: db, auth, trpc, ui.
Data layer uses PostgreSQL with RLS enabled on all tenancy tables.
Payments processed via Stripe Connect with funds separation between organisations.
""".strip(),
        encoding="utf-8",
    )
    (Path(paths["CHE_PROJECT_DIR"]) / "product_context.md").write_text(
        """
# Product

UK-first ticketing platform: public discovery, secure checkout, administrative panel
for event creators, and scanner app for staff at entrance. Currency GBP.
""".strip(),
        encoding="utf-8",
    )
    specs = Path(paths["CHE_WORKSPACE_SHARED"]) / "specs"
    (specs / "payment.md").write_text(
        """---
title: Payment
status: Approved
domain: engineering
---

Payment uses Stripe Connect. After checkout we create PaymentIntent per transaction,
and store reference in DB. Refunds require admin role and record in audit log.
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
    # Test query. We don't guarantee matches as it depends on FTS5; only guarantee serialisable and no crash.
    r = search_rag(str(wt), "Stripe Connect PaymentIntent", top_k=5, hybrid=True)
    assert isinstance(r, dict)
    json.dumps(r)
    assert "results" in r
    assert isinstance(r["results"], list)
    assert "counts" in r
    # counts must have lexical_matches (via search_state) always >= 0
    assert isinstance(r["counts"]["lexical_matches"], int)
