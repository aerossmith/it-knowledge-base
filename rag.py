#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone RAG over the knowledge base: LangGraph (retrieve -> generate) + LM Studio.

Requires a model loaded in LM Studio (OpenAI-compatible server on localhost:1234).

Usage:
    python rag.py "Как настроить GitLab Runner?"
"""

import os
import sys
from typing import TypedDict

import httpx
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from kb_core import hybrid_search_api

LM_STUDIO_URL = os.environ.get("LM_STUDIO_URL", "http://localhost:1234/v1")
TOP_K = 5


class RAGState(TypedDict):
    question: str
    documents: list[dict]
    answer: str


llm = ChatOpenAI(
    model="local-model",
    base_url=LM_STUDIO_URL,
    api_key="lm-studio",
    temperature=0,
    # localhost call must bypass the user's local proxy (HTTP_PROXY env)
    http_client=httpx.Client(trust_env=False),
)

prompt = ChatPromptTemplate.from_template(
    """Ты — помощник по личной базе знаний (DevOps, AI/LLM, инфраструктура).
Отвечай на вопрос ТОЛЬКО на основе контекста ниже.
Если в контексте нет ответа — прямо скажи об этом, не выдумывай.
В конце ответа перечисли URL использованных источников списком «Источники:».

Контекст:
{context}

Вопрос: {question}

Ответ:"""
)


def retrieve(state: RAGState) -> dict:
    try:
        docs = hybrid_search_api(state["question"], top_k=TOP_K)
    except Exception as e:
        return {"documents": [], "answer": f"Knowledge base API недоступен: {e}"}
    return {"documents": docs}


def generate(state: RAGState) -> dict:
    if state.get("answer"):
        return state
    context = "\n\n".join(
        f"[{d['title']}]({d['url']})\n{d['chunk_text']}" for d in state["documents"]
    )
    messages = prompt.format_messages(context=context, question=state["question"])
    try:
        answer = llm.invoke(messages)
    except Exception as e:
        return {"answer": f"LM Studio не отвечает: {e}"}
    return {"answer": answer.content}


# Graph is intentionally linear for now; grade_documents / rewrite_query
# conditional edges can be added later without restructuring.
graph = StateGraph(RAGState)
graph.add_node("retrieve", retrieve)
graph.add_node("generate", generate)
graph.set_entry_point("retrieve")
graph.add_edge("retrieve", "generate")
graph.add_edge("generate", END)
rag_app = graph.compile()


def ask(question: str) -> dict:
    """Public entry point used by webui.py. Returns {question, documents, answer}."""
    return rag_app.invoke({"question": question, "documents": [], "answer": ""})


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python rag.py "ваш вопрос"')
    result = ask(sys.argv[1])
    print(result["answer"])
