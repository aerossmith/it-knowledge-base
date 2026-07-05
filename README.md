# 📚 IT Knowledge Base

> Личная база знаний: статьи, инструменты, ресурсы по DevOps, AI/LLM, инфраструктуре и не только.

![Total](https://img.shields.io/badge/ссылок-273-blue?style=flat-square)
![Categories](https://img.shields.io/badge/разделов-9-green?style=flat-square)
![Last update](https://img.shields.io/badge/обновлено-июнь_2026-orange?style=flat-square)

---

## 🗂️ Разделы

| Раздел | Описание | Ссылок |
|--------|----------|--------|
| [🤖 AI / LLM / Агенты](catalog/ai-llm.md) | RAG, агенты, MCP, Claude, промпты, fine-tuning | 98 |
| [🐳 Kubernetes / Docker](catalog/k8s-docker.md) | Kubernetes, Docker, Podman, контейнеры, оркестрация | 23 |
| [🔄 CI/CD / GitLab / GitOps](catalog/cicd-gitlab.md) | GitLab CI/CD, GitOps, пайплайны, автоматизация деплоя | 17 |
| [🐧 Linux / DevOps / Инфраструктура](catalog/linux-devops.md) | Linux, bash, VPS, DevOps, SRE, observability, бэкапы | 25 |
| [🔒 Сети / VPN / Безопасность](catalog/network-security.md) | VPN, сети, безопасность, RADIUS, HAProxy, SSH, AD | 23 |
| [🗄️ Базы данных](catalog/databases.md) | PostgreSQL, ClickHouse, SQL, OLAP/OLTP | 7 |
| [💼 Карьера / Рынок / Размышления](catalog/career-thoughts.md) | IT-рынок, карьера, найм, размышления об индустрии | 12 |
| [🛠️ Инструменты](catalog/tools.md) | Pulumi, GoAccess, vLLM, awesome-claude и другие | 17 |
| [🎲 Микс](catalog/mix.md) | Книги, фантастика, православие, виски и прочее личное | 51 |

**Итого: 273 ссылки**

---

## 🔍 Как пользоваться

- **Поиск по репозиторию** — `Ctrl+F` прямо на GitHub или нажми `T` для поиска по файлам
- **Быстрая навигация** — кликай по разделам в таблице выше
- **Обновление** — кидай новые ссылки в `inbox.txt` и запускай `get_titles_v2.py` для автодобавления

---

## 🤖 RAG-пайплайн (Misty Garden)

Семантический поиск по статьям с гибридной retrieving (dense + sparse, RRF fusion).

### Стек

- **Scraping**: trafilatura
- **Embeddings**: BAAI/bge-m3 (dense 1024 + sparse, контекст 8192 токена)
- **Vector DB**: Qdrant (Docker, hybrid search)
- **RAG**: LangGraph + LM Studio (qwen-2.5-14b-instruct)
- **API**: FastAPI (kb_api.py)
- **MCP**: Claude Desktop интеграция
- **Web UI**: Streamlit

### Быстрый старт

Сервисы (Qdrant + kb-api с моделью bge-m3) живут в Docker (WSL2) и стартуют сами при загрузке машины:

```bash
# 1. Поднять сервисы: Qdrant (:6333) + kb-api (:8000, модель запечена в образ)
docker compose up -d --build

# 2. Первичное наполнение (или пополнение) базы — Windows venv:
pip install -r requirements.txt          # один раз
python scrape_articles.py                # ~20-30 мин на полный каталог
python index_articles.py                 # ~5 мин
#    …или одной командой при обновлениях: .\update_kb.ps1

# 3. Поиск через API
curl --noproxy "*" -X POST http://localhost:8000/search -H "Content-Type: application/json" -d '{"query": "gitlab runner"}'

# 4. RAG-чат (нужен LM Studio с моделью на :1234)
python rag.py "Как настроить GitLab Runner?"

# 5. Web UI
streamlit run webui.py
```

> ⚠️ На машине с локальным прокси (HTTP_PROXY=127.0.0.1:…) все клиенты ходят к localhost
> с `trust_env=False` / `--noproxy` — иначе 502 от прокси.

### MCP для Claude Desktop

Добавить в `claude_desktop_config.json`:

```json
"it-knowledge-base": {
    "command": "C:\\Users\\alexandr.p\\source\\it-knowledge-base\\.venv\\Scripts\\python.exe",
    "args": ["C:\\Users\\alexandr.p\\source\\it-knowledge-base\\mcp_server.py"]
}
```

---

## 🛠️ Структура

```
it-knowledge-base/
├── README.md
├── catalog/              # каталоги ссылок (9 разделов)
├── raw/                  # scraped текст (.gitignore)
├── qdrant_storage/       # данные Qdrant (.gitignore)
├── docker-compose.yml    # Qdrant + kb-api
├── Dockerfile            # образ kb-api (torch cpu + запечённый bge-m3)
├── requirements.txt      # полный набор для Windows venv (scrape/index/rag/ui)
├── requirements-api.txt  # минимальный набор для контейнера kb-api
├── update_kb.ps1         # инкрементальное пополнение: scrape → index
├── scrape_articles.py    # Фаза 1: scraping
├── index_articles.py     # Фаза 1: индексация
├── kb_core.py            # общий модуль (модель + поиск)
├── kb_api.py             # FastAPI HTTP API (:8000)
├── mcp_server.py         # MCP stdio сервер
├── rag.py                # LangGraph RAG + LM Studio
├── webui.py              # Streamlit Web UI
├── get_titles_v2.py      # парсинг заголовков
└── AGENT_PROMPT.md       # ТЗ для агента
```
