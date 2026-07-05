#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scrape article text from catalog/*.md links via trafilatura.

Output: raw/articles.jsonl (url, title, text, author, date, sitename, category)
Failed URLs (fetch error / text < 150 chars) go to raw/failed_urls.txt.
Already scraped or indexed URLs are skipped, so reruns are incremental.

Usage:
    python scrape_articles.py                       # full run, all categories except mix
    python scrape_articles.py --category ai-llm --limit 15   # test run
"""

import argparse
import json
import pathlib
import random
import re
import sys
import time
from urllib.parse import urlparse

import trafilatura

CATALOG_DIR = pathlib.Path("catalog")
RAW_DIR = pathlib.Path("raw")
ARTICLES_FILE = RAW_DIR / "articles.jsonl"
INDEXED_FILE = RAW_DIR / "indexed_urls.txt"
FAILED_FILE = RAW_DIR / "failed_urls.txt"

EXCLUDED_CATEGORIES = {"mix"}          # non-technical content, not part of RAG
MIN_TEXT_LEN = 150                     # quality filter

DOMAIN_DELAY = {
    "habr.com": (3.0, 5.0),            # habr bans aggressive scraping
    "default":  (0.5, 1.0),
}
RETRY_DELAY = (8.0, 12.0)              # pause before the single retry on fetch failure

URL_RE = re.compile(r"\[→\]\((https?://[^)]+)\)")


def polite_sleep(url: str) -> None:
    domain = urlparse(url).netloc.removeprefix("www.")
    lo, hi = DOMAIN_DELAY.get(domain, DOMAIN_DELAY["default"])
    time.sleep(random.uniform(lo, hi))


def extract_catalog_entries(category_filter: str | None = None) -> list[dict]:
    """Return [{url, title, category}] from catalog/*.md, excluding mix."""
    entries = []
    for md in sorted(CATALOG_DIR.glob("*.md")):
        category = md.stem
        if category in EXCLUDED_CATEGORIES:
            continue
        if category_filter and category != category_filter:
            continue
        for line in md.read_text(encoding="utf-8").splitlines():
            m = URL_RE.search(line)
            if not m:
                continue
            cells = [c.strip() for c in line.split("|")]
            title = cells[2] if len(cells) > 3 else ""
            entries.append({"url": m.group(1).rstrip("/"), "title": title, "category": category})
    return entries


def load_done_urls() -> set[str]:
    """URLs already scraped (articles.jsonl) or indexed (indexed_urls.txt)."""
    done = set()
    if ARTICLES_FILE.exists():
        for line in ARTICLES_FILE.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["url"].rstrip("/"))
            except (json.JSONDecodeError, KeyError):
                continue
    if INDEXED_FILE.exists():
        done.update(u.rstrip("/") for u in INDEXED_FILE.read_text(encoding="utf-8").splitlines() if u.strip())
    return done


def scrape_url(url: str) -> dict | None:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return None
    result = trafilatura.extract(
        downloaded,
        output_format="json",
        include_comments=False,
        include_tables=True,
        include_images=False,
    )
    if not result:
        return None
    data = json.loads(result)
    return {
        "url": url,
        "title": data.get("title") or "",
        "text": data.get("text") or "",
        "author": data.get("author") or "",
        "date": data.get("date") or "",
        "sitename": data.get("sitename") or "",
    }


def log_failed(url: str, reason: str) -> None:
    with open(FAILED_FILE, "a", encoding="utf-8") as f:
        f.write(f"{url}\t{reason}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", help="scrape only this catalog category")
    parser.add_argument("--limit", type=int, help="max number of URLs to process")
    args = parser.parse_args()

    RAW_DIR.mkdir(exist_ok=True)

    entries = extract_catalog_entries(args.category)
    done = load_done_urls()
    todo = [e for e in entries if e["url"] not in done]
    skipped = len(entries) - len(todo)
    if args.limit:
        todo = todo[: args.limit]

    print(f"Catalog entries: {len(entries)}, already done: {skipped}, to scrape: {len(todo)}")

    ok, failed = 0, 0
    for i, entry in enumerate(todo, 1):
        url = entry["url"]
        print(f"[{i}/{len(todo)}] {url[:80]}", end=" ", flush=True)
        try:
            data = scrape_url(url)
        except Exception as e:
            data = None
            print(f"EXC {type(e).__name__}", end=" ")
        if data is None:
            # single retry with a long pause — rescues transient blocks/timeouts
            time.sleep(random.uniform(*RETRY_DELAY))
            try:
                data = scrape_url(url)
                if data is not None:
                    print("(retry ok)", end=" ")
            except Exception:
                data = None
        if data and len(data["text"]) >= MIN_TEXT_LEN:
            data["category"] = entry["category"]
            if not data["title"]:
                data["title"] = entry["title"]
            with open(ARTICLES_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
            ok += 1
            print(f"OK ({len(data['text'])} chars)")
        else:
            reason = "no_content" if not data else f"too_short_{len(data['text'])}"
            log_failed(url, reason)
            failed += 1
            print(f"FAIL ({reason})")
        if i < len(todo):
            polite_sleep(url)

    total = ok + failed
    yield_pct = (ok / total * 100) if total else 0.0
    print(f"\nDone: {ok} ok, {failed} failed out of {total}")
    print(f"Yield: {yield_pct:.1f}%")
    if total and yield_pct < 70:
        print("WARNING: yield below 70% threshold — investigate before full run")
        sys.exit(1)


if __name__ == "__main__":
    main()
