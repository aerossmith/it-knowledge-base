# 📚 IT Knowledge Base

> Личная база знаний: статьи, инструменты, ресурсы по DevOps, AI/LLM, инфраструктуре и не только.

![Total](https://img.shields.io/badge/ссылок-272-blue?style=flat-square)
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
| [🎲 Микс](catalog/mix.md) | Книги, фантастика, православие, виски и прочее личное | 50 |

**Итого: 272 ссылки**

---

## 🔍 Как пользоваться

- **Поиск по репозиторию** — `Ctrl+F` прямо на GitHub или нажми `T` для поиска по файлам
- **Быстрая навигация** — кликай по разделам в таблице выше
- **Обновление** — кидай новые ссылки в `inbox.txt` и запускай `get_titles_v2.py` для автодобавления

---

## 🛠️ Структура

```
it-knowledge-base/
├── README.md           # этот файл
├── get_titles_v2.py    # скрипт для парсинга заголовков (с дедупом и inbox.txt)
└── catalog/
    ├── ai-llm.md
    ├── k8s-docker.md
    ├── cicd-gitlab.md
    ├── linux-devops.md
    ├── network-security.md
    ├── databases.md
    ├── career-thoughts.md
    ├── tools.md
    └── mix.md
```
