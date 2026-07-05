#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Streamlit UI for the knowledge base: hybrid search + RAG chat.

Usage:
    streamlit run webui.py
"""

import streamlit as st

from kb_core import CATEGORIES, hybrid_search_api

st.set_page_config(page_title="IT Knowledge Base", page_icon="📚", layout="wide")
st.title("📚 IT Knowledge Base")

tab_search, tab_chat = st.tabs(["🔍 Поиск", "💬 Чат (RAG)"])

with tab_search:
    col1, col2 = st.columns([4, 1])
    with col1:
        query = st.text_input("Запрос", placeholder="как настроить gitlab runner")
    with col2:
        category = st.selectbox("Категория", ["все"] + CATEGORIES)

    if query:
        with st.spinner("Ищу..."):
            try:
                results = hybrid_search_api(query, None if category == "все" else category, top_k=10)
            except Exception as e:
                st.error(f"Ошибка поиска: {e}\n\nПроверь что kb_api запущен: `.venv\\Scripts\\python.exe kb_api.py`")
                results = []
        if not results:
            st.info("Ничего не найдено.")
        for r in results:
            with st.container(border=True):
                st.markdown(f"**[{r['title']}]({r['url']})**")
                st.caption(f"`{r['category']}` · score {r['score']:.3f}")
                st.write(r["chunk_text"][:600] + ("…" if len(r["chunk_text"]) > 600 else ""))

with tab_chat:
    st.caption("Ответы генерирует локальная модель через LM Studio (localhost:1234) — он должен быть запущен.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg.get("sources"):
                with st.expander("Источники"):
                    for s in msg["sources"]:
                        st.markdown(f"- [{s['title']}]({s['url']}) `{s['category']}`")

    if question := st.chat_input("Вопрос к базе знаний"):
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            with st.spinner("Думаю..."):
                try:
                    from rag import ask
                    result = ask(question)
                    answer = result["answer"]
                    sources = result["documents"]
                except Exception as e:
                    answer = f"Ошибка: {e}\n\nПроверь что LM Studio запущен с моделью на localhost:1234."
                    sources = []
            st.write(answer)
            if sources:
                with st.expander("Источники"):
                    for s in sources:
                        st.markdown(f"- [{s['title']}]({s['url']}) `{s['category']}`")
        st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
