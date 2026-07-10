# Backlog — идеи для следующих итераций

- [ ] **`POST /embed` в kb-api** — чтобы `index_articles.py` не грузил вторую копию модели
      в Windows-venv, а эмбеддил через контейнер (кандидат №1)
- [ ] **Миграция с Docker Desktop на нативный dockerd в WSL** — плюсы: без GUI-зависимости;
      минусы/работа: systemd в wsl.conf, автостарт WSL при логине, проверка localhost-forwarding
      после ребута. Делать отдельной итерацией, не смешивать движки
- [ ] **GPU для эмбеддингов** — GPU есть, но: query-эмбеддинг на CPU ~200мс (не болит),
      CUDA-образ +6GB, VRAM делится с Qwen в LM Studio (8.4GB). Стоит делать только
      вместе с /embed при массовой переиндексации
- [ ] **Reranker bge-reranker-v2-m3** — топ-20 из hybrid → reranker → топ-5; следующий
      буст качества после title-префикса
- [ ] **Полный Contextual Retrieval** (LLM-контекст для каждого чанка через ночной Qwen) —
      когда база вырастет или появятся серии однотипных документов; см. habr 1054594
- [ ] **Расширить golden set** в smoke_test.py до 15-20 вопросов
- [ ] Пины зависимостей (`pip freeze > requirements.lock.txt`), non-root user в Dockerfile
