#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared core for Misty Garden: bge-m3 model access and hybrid search.

Used by index_articles.py, mcp_server.py, rag.py and webui.py — do not duplicate
embedding or search logic elsewhere.
"""

from qdrant_client import QdrantClient, models

import os

# Proxy env vars are deliberately left intact: scrape_articles.py imports this module
# and needs the user's proxy for geo-blocked sites. Local calls (Qdrant, kb_api)
# bypass the proxy per-client via trust_env=False instead.

QDRANT_URL = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")
# HF repo id by default; container sets a local dir (onnx-free snapshot, no hub validation)
BGE_M3_PATH = os.environ.get("BGE_M3_PATH", "BAAI/bge-m3")
COLLECTION = "kb"

CATEGORIES = [
    "ai-llm", "k8s-docker", "cicd-gitlab", "linux-devops",
    "network-security", "databases", "career-thoughts", "tools",
]

_model = None
_client = None

KB_API_URL = os.environ.get("KB_API_URL", "http://127.0.0.1:8000")


def hybrid_search_api(query: str, category: str | None = None, top_k: int = 5) -> list[dict]:
    """Same as hybrid_search, but via the running kb_api service — no model load
    in the calling process. trust_env=False: local call must bypass the user's proxy."""
    import httpx
    resp = httpx.post(
        f"{KB_API_URL}/search",
        json={"query": query, "category": category, "top_k": top_k},
        timeout=60,
        trust_env=False,
    )
    resp.raise_for_status()
    return resp.json()


def get_model():
    """Lazy singleton for BGEM3FlagModel (~2.2GB download on first use).

    stdout is redirected to stderr during load: FlagEmbedding prints progress,
    and any stdout noise corrupts the JSON-RPC stream when running as MCP stdio server.
    """
    global _model
    if _model is None:
        import contextlib
        import os
        import sys
        # Model is fully cached; skip HF Hub network checks (they hang under rate limiting)
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        from FlagEmbedding import BGEM3FlagModel
        with contextlib.redirect_stdout(sys.stderr):
            _model = BGEM3FlagModel(BGE_M3_PATH, use_fp16=True)
    return _model


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        # trust_env=False is forwarded to httpx: local Qdrant must bypass the user's proxy
        _client = QdrantClient(url=QDRANT_URL, trust_env=False)
    return _client


def to_sparse_vector(lexical_weights: dict) -> models.SparseVector:
    """Convert bge-m3 lexical_weights {token_id: weight} to Qdrant SparseVector."""
    return models.SparseVector(
        indices=[int(k) for k in lexical_weights.keys()],
        values=[float(v) for v in lexical_weights.values()],
    )


def embed_texts(texts: list[str]) -> tuple[list, list]:
    """Return (dense_vecs, sparse_vecs) for a batch of texts.

    stdout redirected for the same reason as in get_model() — MCP stdio safety.
    """
    import contextlib
    import sys
    with contextlib.redirect_stdout(sys.stderr):
        out = get_model().encode(texts, return_dense=True, return_sparse=True)
    dense = [v.tolist() for v in out["dense_vecs"]]
    sparse = [to_sparse_vector(w) for w in out["lexical_weights"]]
    return dense, sparse


def hybrid_search(query: str, category: str | None = None, top_k: int = 5) -> list[dict]:
    """Hybrid (dense + sparse, RRF fusion) search over the knowledge base.

    Returns [{title, url, category, chunk_text, score}, ...], deduplicated by URL
    (best-scored chunk per article). category: optional filter, one of CATEGORIES.
    """
    dense, sparse = embed_texts([query])
    query_filter = None
    if category:
        query_filter = models.Filter(
            must=[models.FieldCondition(key="category", match=models.MatchValue(value=category))]
        )
    # Overfetch x3, then keep the best chunk per article so top_k covers distinct sources
    fetch_limit = top_k * 3
    res = get_client().query_points(
        collection_name=COLLECTION,
        prefetch=[
            models.Prefetch(query=dense[0], using="dense", limit=fetch_limit * 2, filter=query_filter),
            models.Prefetch(query=sparse[0], using="sparse", limit=fetch_limit * 2, filter=query_filter),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        query_filter=query_filter,
        limit=fetch_limit,
        with_payload=True,
    )
    results, seen_urls = [], set()
    for p in res.points:
        url = p.payload.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        results.append(
            {
                "title": p.payload.get("title", ""),
                "url": url,
                "category": p.payload.get("category", ""),
                "chunk_text": p.payload.get("text", ""),
                "score": p.score,
            }
        )
        if len(results) >= top_k:
            break
    return results
