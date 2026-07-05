# VAR: it-knowledge-base → RAG Knowledge Base

## Текущее состояние

- ~274 ссылки в `catalog/*.md` (только URL + заголовок)
- Скрипт `get_titles_v2.py` для парсинга заголовков
- Каталоги: ai-llm, k8s-docker, cicd-gitlab, linux-devops, network-security, databases, career-thoughts, tools, mix

## Цель

Превратить каталог ссылок в полноценную базу знаний с:
1. Сырым текстом статей (scraping)
2. Векторными эмбеддингами для семантического поиска
3. RAG-пайплайном для вопросов по базе

---

## Архитектура

```
catalog/*.md → Scraper (trafilatura) → Chunks + Embeddings → ChromaDB
User Query → LangGraph RAG Agent → Retriever ← ChromaDB
```

---

## Этап 1: Scraping (извлечение текста)

### Инструмент: trafilatura

Почему trafilatura:
- Production-grade, лучший в бенчмарках по извлечению контента
- Поддерживает markdown, JSON, TXT на выходе
- Извлекает метаданные (автор, дата, заголовок)
- Работает с русским контентом (habr.com и др.)
- Apache 2.0, активно поддерживается

```bash
pip install trafilatura
```

### Скрипт: `scrape_articles.py`

```python
import trafilatura
import json
import pathlib
import re
import time

CATALOG_DIR = pathlib.Path("catalog")
RAW_DIR = pathlib.Path("raw")
RAW_DIR.mkdir(exist_ok=True)

def extract_urls_from_catalog():
    urls = []
    url_re = re.compile(r'https?://[^\s)\]"\'>]+')
    for md in CATALOG_DIR.glob("*.md"):
        content = md.read_text(encoding="utf-8")
        for m in url_re.findall(content):
            urls.append(m.rstrip("/"))
    return list(set(urls))

def scrape_url(url: str) -> dict | None:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return None
    result = trafilatura.extract(
        downloaded,
        output_format="json",
        include_comments=False,
        include_tables=True,
        include_links=True,
        include_images=False,
        favor_recall=True,
    )
    if not result:
        return None
    data = json.loads(result)
    return {
        "url": url,
        "title": data.get("title", ""),
        "text": data.get("text", ""),
        "author": data.get("author", ""),
        "date": data.get("date", ""),
        "sitename": data.get("sitename", ""),
    }

def main():
    urls = extract_urls_from_catalog()
    print(f"Найдено {len(urls)} уникальных URL")
    results = []
    for i, url in enumerate(urls):
        print(f"[{i+1}/{len(urls)}] {url[:80]}...", end=" ")
        data = scrape_url(url)
        if data and data["text"]:
            results.append(data)
            print(f"✓ ({len(data['text'])} chars)")
        else:
            print("✗ (нет контента)")
        time.sleep(0.5)
    output_file = RAW_DIR / "articles.jsonl"
    with open(output_file, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nСохранено {len(results)} статей в {output_file}")

if __name__ == "__main__":
    main()
```

---

## Этап 2: Chunking

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
    length_function=len,
)

def chunk_article(article: dict) -> list[dict]:
    chunks = splitter.split_text(article["text"])
    return [{
        "text": chunk,
        "metadata": {
            "url": article["url"],
            "title": article["title"],
            "chunk_index": i,
            "total_chunks": len(chunks),
        }
    } for i, chunk in enumerate(chunks)]
```

---

## Этап 3: Embeddings (рекомендация: sentence-transformers)

```bash
pip install sentence-transformers
```

```python
from sentence_transformers import SentenceTransformer

MODEL_NAME = "intfloat/multilingual-e5-large"  # 568M, отличное качество для русского
model = SentenceTransformer(MODEL_NAME)

def embed_chunks(chunks: list[dict]):
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)
    return list(zip(embeddings.tolist(), [c["metadata"] for c in chunks]))
```

**Характеристики:**
- ~568MB на диске, ~1-2GB RAM
- ~1000 чанков/мин на CPU
- ~274 статьи × ~5 чанков = ~1400 чанков → ~1.5 мин

---

## Этап 4: ChromaDB (векторная БД)

```bash
pip install langchain-chroma
```

```python
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-large")

vector_store = Chroma(
    collection_name="knowledge_base",
    embedding_function=embeddings,
    persist_directory="./chroma_db",
)

# Добавление
documents = [Document(page_content=c["text"], metadata=c["metadata"]) for c in all_chunks]
vector_store.add_documents(documents)

# Поиск
results = vector_store.similarity_search("как настроить GitLab CI/CD", k=5)
```

**Размер:** ~10-15MB на диске.

---

## Этап 5: RAG Pipeline (LangGraph)

```python
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from typing import TypedDict

class RAGState(TypedDict):
    question: str
    documents: list
    answer: str

llm = ChatOpenAI(
    model="local-model",
    openai_api_base="http://localhost:1234/v1",  # LM Studio
    openai_api_key="lm-studio",
    temperature=0,
)

prompt = ChatPromptTemplate.from_template("""
Ты — помощник по базе знаний. Отвечай на основе контекста.
Если ответа нет — скажи об этом.

Контекст:
{context}

Вопрос: {question}

Ответ:""")

retriever = vector_store.as_retriever(search_kwargs={"k": 5})

def retrieve(state):
    return {"documents": retriever.invoke(state["question"]), "question": state["question"]}

def generate(state):
    context = "\n\n".join([d.page_content for d in state["documents"]])
    answer = llm.invoke(prompt.format(context=context, question=state["question"]))
    return {"answer": answer.content, "documents": state["documents"]}

graph = StateGraph(RAGState)
graph.add_node("retrieve", retrieve)
graph.add_node("generate", generate)
graph.add_edge("retrieve", "generate")
graph.add_edge("generate", END)
graph.set_entry_point("retrieve")
rag_app = graph.compile()

result = rag_app.invoke({"question": "Как настроить GitLab Runner?"})
```

---

## Этап 6: CLI

```python
# cli.py
import click

@click.group()
def cli():
    pass

@cli.command()
@click.argument("url")
def ingest(url):
    """Добавить статью в базу"""
    pass

@cli.command()
@click.argument("query")
@click.option("--top", default=5)
def search(query, top):
    """Поиск по базе знаний"""
    pass

@cli.command()
@click.argument("question")
def ask(question):
    """Задать вопрос базе (RAG)"""
    pass

if __name__ == "__main__":
    cli()
```

---

## Зависимости

```
trafilatura>=2.0
sentence-transformers>=3.0
langchain>=0.3
langchain-chroma>=0.1
langchain-community>=0.3
langchain-openai>=0.2
chromadb>=0.5
click>=8.0
```

---

## Структура проекта

```
it-knowledge-base/
├── catalog/              # исходные каталоги ссылок
├── raw/                  # сырые данные статей
│   ├── articles.jsonl
│   └── cache/
├── chroma_db/            # векторная база
├── scrape_articles.py    # скрейпер
├── index_articles.py     # индексация
├── rag.py                # RAG pipeline
├── cli.py                # CLI
├── requirements.txt
└── README.md
```

---

## Порядок реализации

1. `scrape_articles.py` — скрейпинг через trafilatura
2. `index_articles.py` — chunking + embedding + ChromaDB
3. `rag.py` — RAG chain (retrieve → generate)
4. `cli.py` — CLI для ingest/search/ask
5. Тестирование на 10-20 статьях, потом на всех

---

Оценка: ~4-5 часов, низкая-средняя сложность
