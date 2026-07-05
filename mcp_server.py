#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP stdio server for the knowledge base — thin client over kb_api.py.

No torch/model in this process: heavy lifting lives in the long-running
kb_api service (localhost:8000), so this server starts instantly and the
stdio JSON-RPC stream stays clean.

Requires kb_api.py running:  .venv\\Scripts\\python.exe kb_api.py

Register in claude_desktop_config.json (absolute paths):
    "it-knowledge-base": {
        "command": "C:\\Users\\alexandr.p\\source\\it-knowledge-base\\.venv\\Scripts\\python.exe",
        "args": ["C:\\Users\\alexandr.p\\source\\it-knowledge-base\\mcp_server.py"]
    }
"""

import httpx
from mcp.server.fastmcp import FastMCP

KB_API = "http://127.0.0.1:8000"

mcp = FastMCP("it-knowledge-base")


@mcp.tool()
def kb_search(query: str, category: str | None = None, top_k: int = 5) -> list[dict]:
    """Семантический поиск по личной базе знаний (222 технические статьи:
    DevOps, AI/LLM, Kubernetes, CI/CD, сети, базы данных).

    query: поисковый запрос на русском или английском.
    category: опциональный фильтр — ai-llm | k8s-docker | cicd-gitlab | linux-devops |
              network-security | databases | career-thoughts | tools.
    top_k: сколько результатов вернуть (default 5).

    Возвращает список {title, url, category, chunk_text, score}.
    """
    try:
        resp = httpx.post(
            f"{KB_API}/search",
            json={"query": query, "category": category, "top_k": top_k},
            timeout=60,
            trust_env=False,
        )
    except httpx.ConnectError:
        raise ValueError("kb_api service is not running. Start it: "
                         ".venv\\Scripts\\python.exe kb_api.py (in it-knowledge-base repo)")
    if resp.status_code != 200:
        raise ValueError(f"kb_api returned {resp.status_code}: {resp.text[:200]}")
    return resp.json()


if __name__ == "__main__":
    mcp.run()
