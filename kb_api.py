#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Long-running search service over the knowledge base.

Loads bge-m3 once at startup and serves hybrid search over HTTP.
Consumers: mcp_server.py (thin client), webui.py, rag.py, n8n, curl.

Usage:
    .venv\\Scripts\\python.exe kb_api.py          # serves on http://localhost:8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from kb_core import CATEGORIES, get_model, hybrid_search


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_model()  # load once at startup (~20s), all requests are fast afterwards
    yield


app = FastAPI(title="it-knowledge-base search API", lifespan=lifespan)


class SearchRequest(BaseModel):
    query: str
    category: str | None = None
    top_k: int = 5


@app.get("/health")
def health() -> dict:
    try:
        from kb_core import get_client
        get_client().get_collection("kb")
        return {"status": "ok", "qdrant": "connected", "categories": CATEGORIES}
    except Exception as e:
        raise HTTPException(503, detail=f"Qdrant unavailable: {e}")


@app.post("/search")
def search(req: SearchRequest) -> list[dict]:
    if req.category and req.category not in CATEGORIES:
        raise HTTPException(422, f"Unknown category '{req.category}'. Valid: {', '.join(CATEGORIES)}")
    return hybrid_search(req.query, req.category, req.top_k)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
