#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke + retrieval quality test against the running kb-api.

Golden set: question -> URL fragment that must appear in top-5.
Run after every reindex / model / chunking change:
    .venv\\Scripts\\python.exe smoke_test.py
Exit code 0 = all good, 1 = something degraded.
"""

import sys

import httpx

KB_API = "http://127.0.0.1:8000"

# (query, url_fragment_expected_in_top5)
GOLDEN = [
    ("настройка self-hosted gitlab runner", "habr.com/ru/articles/1032654"),
    ("что такое RAG система", "habr.com/ru/articles/1029740"),
    ("бесплатные vpn конфигурации для россии", "github.com/igareck/vpn-configs"),
    ("развернуть kubernetes кластер proxmox", "habr.com/ru/articles/942304"),
    ("поиск узких мест производительности linux", "habr.com/ru/companies/ruvds/articles/1000218"),
    ("mcp сервер для windows администрирования", "habr.com"),
    ("docker образы уменьшение размера слоёв", "habr.com"),
    ("выбор embedding модели для русского языка", "habr.com"),
]


def main() -> int:
    client = httpx.Client(trust_env=False, timeout=60)

    r = client.get(f"{KB_API}/health")
    assert r.status_code == 200 and r.json()["status"] == "ok", f"health failed: {r.text}"
    print(f"health: OK ({r.json().get('qdrant', '?')})")

    failed = 0
    for query, expected in GOLDEN:
        results = client.post(f"{KB_API}/search", json={"query": query, "top_k": 5}).json()
        urls = " ".join(r["url"] for r in results)
        ok = expected in urls
        print(f"  {'PASS' if ok else 'FAIL'}  {query[:50]:<52} -> {expected[:45]}")
        if not ok:
            failed += 1

    print(f"\n{len(GOLDEN) - failed}/{len(GOLDEN)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
