# ТЗ: Misty Garden — RAG Knowledge Base (репозиторий: it-knowledge-base)

> Это самодостаточное задание для рабочего агента. Исходная идея проекта — в `VAR.md` (история,
> НЕ актуальна как спецификация: стек там устарел). Актуальная спецификация — этот файл.

## Контекст

Репозиторий: `C:\Users\alexandr.p\source\it-knowledge-base` / `https://github.com/aerossmith/it-knowledge-base`

Личная база знаний: 222 технические ссылки в `catalog/*.md` (8 файлов: ai-llm, k8s-docker,
cicd-gitlab, linux-devops, network-security, databases, career-thoughts, tools).
mix.md — не входит в RAG (нетехнический контент).
Формат строк каталога: `| N | Заголовок статьи | [→](https://url) |`

**Задача**: реализовать RAG-пайплайн поверх каталога с тремя интерфейсами:
1. **MCP-сервер** — поиск по базе из Claude Desktop/Code (без LLM, генерацию делает Claude)
2. **Автономный RAG** — LangGraph + LM Studio, работает офлайн
3. **Web UI** — Streamlit: поиск + чат

Архитектура:
```
catalog/*.md → scrape (trafilatura) → chunk → bge-m3 (dense+sparse) → Qdrant (Docker)
                                                                         │
                                                                    kb_api.py (FastAPI :8000)
                                                                    /  (загружает bge-m3 один раз)
                                                                   / \
                                                                  /   \
                                                         mcp_server.py   rag.py → LM Studio
                                                         (MCP stdio)      (LangGraph)
                                                                       \
                                                                webui.py (Streamlit)
```

kb_api.py — long-running HTTP-сервис, загружает bge-m3 при старте (~20 сек).
MCP-сервер, rag.py и webui.py — тонкие клиенты через `hybrid_search_api()` (httpx),
не грузят модель в своём процессе. kb_core.py используется напрямую только
index_articles.py (при индексации).

---

## Стек (утверждён, не менять)

| Компонент | Решение |
|-----------|---------|
| Scraping | trafilatura (БЕЗ `favor_recall`, БЕЗ `include_links`) |
| Chunking | `RecursiveCharacterTextSplitter`, size=1000, overlap=200 |
| Embeddings | `BAAI/bge-m3` через `FlagEmbedding.BGEM3FlagModel` — dense (1024) + sparse, контекст 8192 |
| Vector DB | Qdrant в Docker, hybrid search (RRF fusion), web UI на :6333 |
| Оркестрация RAG | LangGraph (StateGraph) |
| LLM (только для rag.py) | LM Studio, OpenAI-compatible endpoint `http://localhost:1234/v1` |
| MCP | python `mcp` SDK (FastMCP), stdio transport |
| Search API | FastAPI + uvicorn на `http://localhost:8000` (kb_api.py) |
| Web UI | Streamlit |

### Lang*-пакеты: что ставить, что НЕТ

Ставить: `langgraph`, `langchain-openai`, `langchain-text-splitters`.

НЕ ставить: `langchain` (мета-пакет — не нужен целиком), `langchain-community` (legacy),
`langchain-qdrant` (hybrid делаем напрямую через `qdrant-client` Query API),
`langchain-huggingface` (embeddings напрямую через FlagEmbedding), LangSmith, LangServe.

Retrieve-нода LangGraph — обычная Python-функция с `qdrant_client.query_points()`,
LangChain-абстракция retriever не используется.

---

## requirements.txt

```
trafilatura>=2.0
FlagEmbedding>=1.2
qdrant-client>=1.12
langgraph>=0.2
langchain-openai>=0.2
langchain-text-splitters>=0.3
mcp>=1.0
streamlit>=1.40
fastapi>=0.115
uvicorn>=0.32
httpx>=0.27
```

---

## docker-compose.yml — Qdrant + kb-api (рабочая логика в WSL2)

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: kb-qdrant
    ports: ["6333:6333", "6334:6334"]
    volumes: ["./qdrant_storage:/qdrant/storage"]
    restart: unless-stopped

  kb-api:
    build: .                     # Dockerfile: python:3.12-slim + torch cpu + запечённый bge-m3
    container_name: kb-api
    ports: ["8000:8000"]
    environment: ["QDRANT_URL=http://qdrant:6333"]
    depends_on: [qdrant]
    restart: unless-stopped
```

Модель запекается в образ на этапе build (`RUN python -c "...BGEM3FlagModel('BAAI/bge-m3')"`),
рантайм полностью офлайн (`HF_HUB_OFFLINE=1`) — нет зависаний на проверках HF Hub.
Автостарт: Docker Desktop стартует при логине + `restart: unless-stopped` — Task Scheduler не нужен.

---

## Структура проекта (целевая)

```
it-knowledge-base/
├── catalog/              # исходные каталоги — НЕ трогать
├── raw/
│   ├── articles.jsonl    # scraped текст
│   ├── indexed_urls.txt  # уже проиндексированные URL (инкрементальность)
│   └── failed_urls.txt   # 403/пустые — для ручного разбора
├── qdrant_storage/       # volume Qdrant
├── docker-compose.yml
├── scrape_articles.py    # Фаза 1
├── index_articles.py     # Фаза 1
├── kb_core.py            # общий модуль: модель + hybrid_search (для индексации)
├── kb_api.py             # Фаза 1.5: FastAPI search-сервис (:8000), загружает bge-m3
├── mcp_server.py         # Фаза 2: MCP stdio, тонкий клиент kb_api
├── rag.py                # Фаза 3: LangGraph + LM Studio, клиент kb_api
├── webui.py              # Фаза 4: Streamlit, клиент kb_api
├── requirements.txt
└── AGENT_PROMPT.md       # этот файл
```

В `.gitignore` добавить: `raw/`, `qdrant_storage/`.

---

## Технические требования (обязательные)

### 1. Scraping: per-domain rate limit + quality filter

```python
import random, time
from urllib.parse import urlparse

DOMAIN_DELAY = {
    "habr.com": (3.0, 5.0),   # random в диапазоне; habr банит агрессивный скрейпинг
    "default":  (0.5, 1.0),
}

def polite_sleep(url: str):
    domain = urlparse(url).netloc.removeprefix("www.")
    lo, hi = DOMAIN_DELAY.get(domain, DOMAIN_DELAY["default"])
    time.sleep(random.uniform(lo, hi))
```

- trafilatura: `extract(downloaded, output_format="json", include_comments=False, include_tables=True, include_images=False)` — БЕЗ `favor_recall`, БЕЗ `include_links`
- Quality filter: `if not data or len(data.get("text", "")) < 150: → failed_urls.txt, skip`
- Успешные → `raw/articles.jsonl` (url, title, text, author, date, sitename, category)
- category берётся из имени файла каталога, где найден URL (ai-llm, k8s-docker, ...)
- URL уже присутствующие в `raw/indexed_urls.txt` — пропускать (инкрементальность)

### 2. Индексация: bge-m3 hybrid → Qdrant

```python
from FlagEmbedding import BGEM3FlagModel
from qdrant_client import QdrantClient, models
import uuid

model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)

# Коллекция: named dense vector + sparse vector
client.create_collection(
    collection_name="kb",
    vectors_config={"dense": models.VectorParams(size=1024, distance=models.Distance.COSINE)},
    sparse_vectors_config={"sparse": models.SparseVectorParams()},
)

# Эмбеддинг чанков
out = model.encode(texts, return_dense=True, return_sparse=True)
# out["dense_vecs"] — dense, out["lexical_weights"] — sparse (dict token_id → weight)
# Qdrant ожидает SparseVector(indices=list, values=list) — нужна конвертация:
#   sparse_vec = models.SparseVector(indices=list(weights.keys()), values=list(weights.values()))

# Идемпотентный upsert: детерминированный id
point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{url}#{chunk_index}"))
```

- Payload каждого point: `url, title, category, chunk_index, text`
- После успешной индексации статьи — дописать её URL в `raw/indexed_urls.txt`
- Повторный запуск `index_articles.py` НЕ создаёт дублей (upsert по uuid5)

### 3. kb_core.py — единая точка доступа (для индексации)

index_articles.py импортирует напрямую из kb_core. MCP-сервер, rag.py и webui.py — через kb_api.py:

```python
# kb_core.py
def get_model():          # ленивая загрузка BGEM3FlagModel (singleton)
def hybrid_search(query: str, category: str | None = None, top_k: int = 5) -> list[dict]:
    """Возвращает [{title, url, category, chunk_text, score}, ...]
    Hybrid: prefetch dense + sparse → FusionQuery(fusion=Fusion.RRF).
    category — опциональный фильтр по payload."""
```

Поиск через Qdrant Query API:
```python
client.query_points(
    collection_name="kb",
    prefetch=[
        models.Prefetch(query=dense_vec, using="dense", limit=20),
        models.Prefetch(query=models.SparseVector(indices=..., values=...), using="sparse", limit=20),
    ],
    query=models.FusionQuery(fusion=models.Fusion.RRF),
    query_filter=models.Filter(...) if category else None,
    limit=top_k,
)
```

### 4. kb_api.py — FastAPI search-сервис

Long-running процесс, загружает bge-m3 один раз при старте (~20 сек). Служит бэкендом для MCP/RAG/WebUI.

```python
# kb_api.py
@app.get("/health")       # проверить что Qdrant доступен (get_collection)
@app.post("/search")       # query, category?, top_k → hybrid_search()
```

- Запуск: контейнер `kb-api` в docker-compose (см. выше); dev-режим на Windows: `.venv\Scripts\python.exe kb_api.py`
- Должен быть запущен ДО MCP-сервера, rag.py и webui.py
- Клиенты: `kb_core.hybrid_search_api()` — httpx POST /search, trust_env=False (bypass proxy)

### 5. mcp_server.py — MCP stdio-сервер

Тонкий HTTP-клиент kb_api.py. Не загружает модель в своём процессе — стартует мгновенно.

```python
import httpx
from mcp.server.fastmcp import FastMCP

KB_API = "http://127.0.0.1:8000"

mcp = FastMCP("misty-garden")

@mcp.tool()
def kb_search(query: str, category: str | None = None, top_k: int = 5) -> list[dict]:
    """Семантический поиск по личной базе знаний (222 статьи: DevOps, AI/LLM, k8s, CI/CD, сети, БД...).
    category: ai-llm | k8s-docker | cicd-gitlab | linux-devops | network-security |
    databases | career-thoughts | tools"""
    resp = httpx.post(
        f"{KB_API}/search",
        json={"query": query, "category": category, "top_k": top_k},
        timeout=60, trust_env=False,
    )
    resp.raise_for_status()
    return resp.json()

if __name__ == "__main__":
    mcp.run()
```

**ВАЖНО**: `claude_desktop_config.json` НЕ редактировать. Выдать пользователю готовый сниппет
для ручного добавления (command: python, args: [абсолютный путь к mcp_server.py]).

### 6. rag.py — LangGraph + LM Studio

- `StateGraph` с TypedDict-состоянием: `question, documents, answer`
- Ноды: `retrieve` (вызывает `kb_core.hybrid_search_api` → kb_api.py) → `generate` (ChatOpenAI → LM Studio)
- `ChatOpenAI(model="local-model", base_url="http://localhost:1234/v1", api_key="lm-studio", temperature=0)`
  — в свежих версиях langchain-openai параметр называется `base_url`, а не `openai_api_base`. Если агент установит старую версию, заменить обратно на `openai_api_base`.
- Промпт на русском: отвечать по контексту, в конце перечислить URL источников; если ответа
  в контексте нет — сказать об этом
- Структура графа готова к добавлению conditional edges (grade_documents → rewrite_query),
  но СЕЙЧАС их НЕ делать — только retrieve → generate → END
- Smoke-test: `python rag.py "Как настроить GitLab Runner?"`

### 7. webui.py — Streamlit

- Вкладка «Поиск»: input + селект категории → `hybrid_search_api` → карточки (title-ссылка,
  category-бейдж, фрагмент текста, score)
- Вкладка «Чат»: история в `st.session_state`, ответы через rag.py, под ответом — источники
- Запуск: `streamlit run webui.py`

---

## Порядок реализации — фазы с контрольными точками

### Фаза 1 — данные (core)
1. `docker-compose.yml` → `docker compose up -d` → проверить `curl http://localhost:6333`
2. `requirements.txt` → `pip install -r requirements.txt`
3. `scrape_articles.py` → **тест на 15 URL из ai-llm.md** (проверить Habr-домен)
   → **КОНТРОЛЬНАЯ ТОЧКА: показать yield пользователю и ждать «ок».
   Yield = (URL с ≥150 символов текста) / (всего URL).
   Если yield < 70% — СТОП, разбираться в причинах, не продолжать.**
4. Полный scraping (~222 URL, ~20-30 мин с учётом delays)
5. `kb_core.py` + `index_articles.py` → проверить количество points в Qdrant UI (localhost:6333/dashboard)
6. `kb_api.py` → запустить: `.venv\Scripts\python.exe kb_api.py` → проверить `curl http://localhost:8000/health`
7. Smoke: `curl -X POST http://localhost:8000/search -H "Content-Type: application/json" -d '{"query":"gitlab runner"}'`
   → возвращает релевантные чанки

### Фаза 2 — MCP-сервер
7. `mcp_server.py` → протестировать (mcp dev / ручной вызов)
8. Выдать пользователю сниппет для `claude_desktop_config.json` (НЕ применять самому)

### Фаза 3 — автономный RAG
9. `rag.py` → перед запуском попросить пользователя запустить LM Studio с моделью
   → smoke: `python rag.py "Как настроить GitLab Runner?"`

### Фаза 4 — Web UI
10. `webui.py` → `streamlit run webui.py` → проверить обе вкладки

**После каждой фазы — короткий отчёт пользователю: что сделано, что работает, что дальше.**

### Критерии приёмки
- `kb_search` из Claude возвращает релевантные чанки со ссылками
- Ответ rag.py опирается на статьи каталога и перечисляет URL источников
- Web UI ищет и отвечает; повторный запуск index_articles.py не плодит дубли

---

## Контекст среды

- Windows 11, PowerShell; Python 3.x; Docker установлен (Windows + WSL); GPU есть (CUDA)
- LM Studio установлен; модель: **qwen-2.5-14b-instruct-1m-k-m**; endpoint `http://localhost:1234/v1`
- Первая загрузка bge-m3 скачает ~2.2GB с HuggingFace — это нормально; `use_fp16=True` (GPU)
- GitHub: `aerossmith`, remote `https://github.com/aerossmith/it-knowledge-base`

## Запреты

- НЕ коммитить и НЕ пушить без явной команды пользователя
- НЕ редактировать `claude_desktop_config.json`, `CLAUDE.md`, `AGENTS.md`
- НЕ удалять и НЕ изменять `catalog/*.md`, `get_titles_v2.py`, `VAR.md`
- Ответы пользователю — на русском; код и комментарии — на английском

## Главный риск

~60% каталога — Habr, который банит агрессивный скрейпинг (мы уже ловили 403 на этом домене).
Если тестовый yield < 70% — останавливаться и разбираться (увеличить delay, сменить User-Agent,
рассмотреть кэширование через `trafilatura.fetch_url` с backoff), а НЕ продолжать полный прогон.
Fallback при тройном 403: попробовать `requests` + BeautifulSoup с явным User-Agent и
извлечением тега `<article>` — но только после согласования с пользователем.
