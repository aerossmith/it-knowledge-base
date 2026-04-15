#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Вытаскивает заголовки страниц по списку URL.
Результат сохраняет в titles_output.tsv (url TAB title)
Запуск: python get_titles.py
Зависимости: pip install requests beautifulsoup4
"""

import requests
from bs4 import BeautifulSoup
import time
import sys

URLS = [
    # === HABR ===
    "https://habr.com/ru/articles/1005776/",
    "https://habr.com/ru/articles/988920/",
    "https://habr.com/ru/companies/flant/articles/928114/",
    "https://habr.com/ru/companies/bcs_company/articles/1006944/",
    "https://habr.com/ru/articles/996722/",
    "https://habr.com/ru/articles/996560/",
    "https://habr.com/ru/companies/ruvds/articles/992050/",
    "https://habr.com/ru/articles/991614/",
    "https://habr.com/ru/companies/k2tech/articles/990556/",
    "https://habr.com/ru/articles/988004/",
    # ... добавляй новые ссылки сюда
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

OUTPUT_FILE = "titles_output.tsv"


def get_title(url: str, session: requests.Session) -> str:
    try:
        r = session.get(url, timeout=15, headers=HEADERS, allow_redirects=True)
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        og = soup.find("meta", property="og:title")
        if og and og.get("content", "").strip():
            return og["content"].strip()
        tag = soup.find("title")
        if tag and tag.text.strip():
            title = tag.text.strip()
            for sep in [" / Хабр", " — Хабр", " | Хабр"]:
                title = title.replace(sep, "")
            return title.strip()
        return "NO_TITLE"
    except Exception as e:
        return f"ERROR: {e}"


def main():
    print(f"Обрабатываю {len(URLS)} ссылок...\n")
    results = []
    with requests.Session() as session:
        for i, url in enumerate(URLS, 1):
            title = get_title(url, session)
            results.append((url, title))
            status = "✓" if not title.startswith("ERROR") and title != "NO_TITLE" else "✗"
            print(f"[{i:3}/{len(URLS)}] {status} {title[:80]}")
            sys.stdout.flush()
            time.sleep(0.4)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("url\ttitle\n")
        for url, title in results:
            f.write(f"{url}\t{title}\n")
    errors = sum(1 for _, t in results if t.startswith("ERROR") or t == "NO_TITLE")
    print(f"\nГотово! Сохранено в {OUTPUT_FILE}")
    print(f"Успешно: {len(results) - errors} / {len(results)}")


if __name__ == "__main__":
    main()
