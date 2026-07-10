#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chunk scraped articles, embed with bge-m3 (dense + sparse) and upsert into Qdrant.

Idempotent: point ids are uuid5(url#chunk_index), reruns overwrite instead of duplicating.
Articles whose URL is already in raw/indexed_urls.txt are skipped.

Usage:
    python index_articles.py            # index everything new from raw/articles.jsonl
    python index_articles.py --limit 5  # test run on first 5 new articles
"""

import argparse
import json
import pathlib
import uuid

from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import models

from kb_core import COLLECTION, embed_texts, get_client

RAW_DIR = pathlib.Path("raw")
ARTICLES_FILE = RAW_DIR / "articles.jsonl"
INDEXED_FILE = RAW_DIR / "indexed_urls.txt"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
BATCH_SIZE = 32

splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def ensure_collection() -> None:
    client = get_client()
    if not client.collection_exists(COLLECTION):
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config={"dense": models.VectorParams(size=1024, distance=models.Distance.COSINE)},
            sparse_vectors_config={"sparse": models.SparseVectorParams()},
        )
        client.create_payload_index(
            collection_name=COLLECTION,
            field_name="category",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )


def load_indexed_urls() -> set[str]:
    if INDEXED_FILE.exists():
        return {u.strip() for u in INDEXED_FILE.read_text(encoding="utf-8").splitlines() if u.strip()}
    return set()


def index_article(article: dict) -> int:
    """Chunk, embed and upsert one article. Returns number of chunks.

    Chunks are embedded with a "title [category]" prefix (poor man's contextual
    retrieval — the title carries the document context lost at chunking), but the
    payload keeps the original chunk text for clean LLM prompts.
    """
    chunks = splitter.split_text(article["text"])
    if not chunks:
        return 0
    prefix = f"{article['title']} [{article['category']}]\n\n"
    client = get_client()
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]
        dense, sparse = embed_texts([prefix + c for c in batch])
        points = []
        for j, chunk in enumerate(batch):
            idx = start + j
            points.append(
                models.PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{article['url']}#{idx}")),
                    vector={"dense": dense[j], "sparse": sparse[j]},
                    payload={
                        "url": article["url"],
                        "title": article["title"],
                        "category": article["category"],
                        "chunk_index": idx,
                        "text": chunk,
                    },
                )
            )
        client.upsert(collection_name=COLLECTION, points=points)
    return len(chunks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="max number of new articles to index")
    args = parser.parse_args()

    if not ARTICLES_FILE.exists():
        raise SystemExit(f"{ARTICLES_FILE} not found — run scrape_articles.py first")

    ensure_collection()
    indexed = load_indexed_urls()

    articles = []
    for line in ARTICLES_FILE.read_text(encoding="utf-8").splitlines():
        a = json.loads(line)
        if a["url"] not in indexed:
            articles.append(a)
    if args.limit:
        articles = articles[: args.limit]

    print(f"New articles to index: {len(articles)} (already indexed: {len(indexed)})")

    total_chunks = 0
    for i, article in enumerate(articles, 1):
        n = index_article(article)
        total_chunks += n
        with open(INDEXED_FILE, "a", encoding="utf-8") as f:
            f.write(article["url"] + "\n")
        print(f"[{i}/{len(articles)}] {article['title'][:60]} — {n} chunks")

    info = get_client().get_collection(COLLECTION)
    print(f"\nIndexed {total_chunks} chunks. Collection now has {info.points_count} points.")


if __name__ == "__main__":
    main()
