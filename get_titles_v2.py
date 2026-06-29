#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Вытаскивает заголовки страниц по списку URL из inbox.txt.

Что нового vs get_titles.py:
  - URL читаются из файла (inbox.txt), а не хардкодятся в коде
  - Дедупликация против ссылок, уже лежащих в catalog/*.md
  - Параллельная обработка (ThreadPoolExecutor) с ограничением потоков
  - Результат в titles_output.tsv (url TAB title) — дальше LLM раскидывает по категориям

Запуск:
    python get_titles_v2.py                # читает inbox.txt, дедуп по catalog/
    python get_titles_v2.py my_urls.txt    # свой файл со ссылками

Зависимости: pip install requests beautifulsoup4
"""

import sys
import re
import time
import pathlib
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

# ── Конфиг ──────────────────────────────────────────────────────────────────
INBOX_FILE   = sys.argv[1] if len(sys.argv) > 1 else "inbox.txt"
CATALOG_DIR  = "catalog"          # откуда берём уже существующие ссылки для дедупа
OUTPUT_FILE  = "titles_output.tsv"
MAX_WORKERS  = 6                  # сколько ссылок тянем параллельно (не задирай — бан)
TIMEOUT      = 15
PAUSE        = 0.15               # пауза между стартами задач, лёгкая

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

TITLE_SUFFIXES = [" / Хабр", " — Хабр", " | Хабр"]


# ── Хелперы ─────────────────────────────────────────────────────────────────
def load_existing_urls(catalog_dir: str) -> set[str]:
    """Собирает все URL, уже упомянутые в catalog/*.md, для дедупа."""
    existing = set()
    cat = pathlib.Path(catalog_dir)
    if not cat.exists():
        return existing
    url_re = re.compile(r'https?://[^\s)\]"\'>]+')
    for md in cat.glob("*.md"):
        for m in url_re.findall(md.read_text(encoding="utf-8", errors="ignore")):
            existing.add(m.rstrip("/"))
    return existing


def read_inbox(path: str) -> list[str]:
    """Читает ссылки построчно. Пустые строки и #комментарии игнорируются."""
    p = pathlib.Path(path)
    if not p.exists():
        print(f"Нет файла {path}. Создай его и кинь туда ссылки по одной на строку.")
        sys.exit(1)
    urls = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def get_title(url: str, session: requests.Session) -> str:
    try:
        r = session.get(url, timeout=TIMEOUT, headers=HEADERS, allow_redirects=True)
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        og = soup.find("meta", property="og:title")
        if og and og.get("content", "").strip():
            return og["content"].strip()

        tag = soup.find("title")
        if tag and tag.text.strip():
            title = tag.text.strip()
            for sep in TITLE_SUFFIXES:
                title = title.replace(sep, "")
            return title.strip()

        return "NO_TITLE"
    except Exception as e:
        return f"ERROR: {e}"


# ── Основной поток ──────────────────────────────────────────────────────────
def main():
    raw_urls = read_inbox(INBOX_FILE)
    existing = load_existing_urls(CATALOG_DIR)

    # дедуп: внутри inbox + против каталога
    seen, new_urls, skipped = set(), [], 0
    for u in raw_urls:
        key = u.rstrip("/")
        if key in seen or key in existing:
            skipped += 1
            continue
        seen.add(key)
        new_urls.append(u)

    print(f"В inbox: {len(raw_urls)} | уже в базе/дубли: {skipped} | к обработке: {len(new_urls)}\n")
    if not new_urls:
        print("Новых ссылок нет, всё уже в базе.")
        return

    results = {}
    with requests.Session() as session:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {}
            for url in new_urls:
                futures[pool.submit(get_title, url, session)] = url
                time.sleep(PAUSE)  # размазываем старты, чтобы не бить пачкой

            done = 0
            for fut in as_completed(futures):
                url = futures[fut]
                title = fut.result()
                results[url] = title
                done += 1
                ok = not title.startswith("ERROR") and title != "NO_TITLE"
                mark = "✓" if ok else "✗"
                print(f"[{done:3}/{len(new_urls)}] {mark} {title[:80]}")
                sys.stdout.flush()

    # сохраняем в исходном порядке inbox
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("url\ttitle\n")
        for url in new_urls:
            f.write(f"{url}\t{results.get(url, 'NO_TITLE')}\n")

    errors = sum(1 for t in results.values() if t.startswith("ERROR") or t == "NO_TITLE")
    print(f"\nГотово! Сохранено в {OUTPUT_FILE}")
    print(f"Успешно: {len(results) - errors} / {len(results)}")
    if errors:
        print(f"Ошибок/пустых: {errors} — их проще добить руками или перезапустить отдельно.")


if __name__ == "__main__":
    main()
