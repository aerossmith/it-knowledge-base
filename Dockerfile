# Misty Garden — hybrid search API (bge-m3 + Qdrant client)
FROM python:3.12-slim

LABEL org.opencontainers.image.title="Misty Garden — search API" \
      org.opencontainers.image.description="Hybrid (dense+sparse, RRF) search API for the Misty Garden knowledge base"

WORKDIR /app

# CPU-only torch first — keeps the image ~3GB smaller than default CUDA build
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# Bake the model into the image as a plain directory, skipping unused ONNX weights
# (~2.3GB saved). A local path avoids hub snapshot validation entirely, so the
# runtime works fully offline — no HF Hub calls, no rate-limit hangs.
RUN python -c "from huggingface_hub import snapshot_download; \
snapshot_download('BAAI/bge-m3', local_dir='/models/bge-m3', ignore_patterns=['onnx/*', '*.onnx', 'imgs/*'])" \
    && rm -rf /root/.cache/huggingface
ENV BGE_M3_PATH=/models/bge-m3 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

# Build-time smoke: the model must load from the local dir with no network
COPY kb_core.py ./
RUN python -c "from kb_core import get_model; get_model(); print('model loads OK')"

COPY kb_api.py ./

EXPOSE 8000
CMD ["uvicorn", "kb_api:app", "--host", "0.0.0.0", "--port", "8000"]
