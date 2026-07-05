# kb-api: hybrid search service (bge-m3 + Qdrant client)
FROM python:3.12-slim

WORKDIR /app

# CPU-only torch first — keeps the image ~3GB smaller than default CUDA build
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# Bake the model into the image (layer cached until deps change above).
# Runtime then works fully offline — no HF Hub calls, no rate-limit hangs.
RUN python -c "from FlagEmbedding import BGEM3FlagModel; BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)"
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

COPY kb_core.py kb_api.py ./

EXPOSE 8000
CMD ["uvicorn", "kb_api:app", "--host", "0.0.0.0", "--port", "8000"]
