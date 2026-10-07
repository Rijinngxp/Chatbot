# ---------------------------------------------------------------------------
# Backend: FastAPI + agents + RAG (ChromaDB, BM25, fastembed models)
# If a dependency has no Python 3.14 wheel on Linux yet, switch to python:3.12-slim.
# ---------------------------------------------------------------------------
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Run as a non-root user; /data (ChromaDB) and /models (embedding + reranker) belong to it.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data /models \
    && chown app:app /data /models

# Dependencies first, so code changes don't reinstall everything.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=app:app app ./app
COPY --chown=app:app run.py .

USER app

# Download the embedding + reranker models (~650 MB) at build time, so containers start fast
# and work without internet access to Hugging Face.
ENV MODEL_CACHE_DIR=/models
RUN python -c "from app.rag.models import dense_model, reranker; dense_model(); reranker()"

# Listen on all interfaces inside the container; keep the vector DB on the /data volume.
ENV HOST=0.0.0.0 \
    PORT=8000 \
    CHROMA_PATH=/data/chroma

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"

CMD ["python", "run.py"]
