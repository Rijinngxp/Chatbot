# Multi-Agent RAG Chatbot

```
greeting:         Planner → Synthesizer
search, web off:   Planner → RAG search → Verifier (question + chunks) → Synthesizer
search, web on:    Planner → Web search → Verifier (question + results) → Synthesizer
```

| Component | Implementation |
|---|---|
| UI | React (Vite) — chat, live pipeline tracker, **Web search** toggle, document upload, sources & verification panel |
| Planner agent | Groq LLM: decides greeting vs search and writes a standalone search query |
| RAG tool | Semantic chunking → ChromaDB (dense `bge-small` vectors) + in-memory BM25 keyword index → RRF hybrid fusion → `bge-reranker-v2-m3` cross-encoder rerank |
| Web search tool | Tavily — used instead of RAG when the UI **Web search** toggle is on |
| Verifier agent | Groq LLM: checks the question against the retrieved chunks (relevance, sufficiency, explicit content) and keeps only the relevant ones |
| Synthesizer agent | Groq LLM: writes the final cited answer from the verified chunks (streamed) |

Everything (models, temperatures, switches, chunking, top-k, reranker, ChromaDB path/host, BM25 params, Tavily depth…) is set in `backend/.env` — see `backend/.env.example`.

## Setup

```bash
# backend
cd backend
cp .env.example .env          # add GROQ_API_KEY and TAVILY_API_KEY
uv pip install -r requirements.txt
../.venv/Scripts/python run.py      # uvicorn on HOST:PORT from .env; API docs at /docs

# frontend (new terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

First start downloads the embedding model (~70 MB) and the bge-reranker-v2-m3 int8 reranker (~570 MB) into `backend/data/models`.

## How a request flows (`backend/app/pipeline.py`)
1. **Planner** decides: greeting → straight to the **Synthesizer**; otherwise writes a standalone search query.
2. **Search**: the knowledge base (semantic chunks → ChromaDB + BM25 → RRF → reranker), or **Tavily** when the UI's Web search toggle is on.
3. **Verifier** checks the question against the retrieved chunks: which are relevant, whether they're enough, and whether anything is explicit (→ blocked). Only relevant chunks continue.
4. **Synthesizer** writes the cited answer from those chunks, saying clearly what's missing if they weren't enough.

The verifier can be turned off with `ENABLE_VERIFIER=false`; RAG with `ENABLE_RAG=false`.

## API endpoints (FastAPI — interactive docs at http://localhost:8000/docs)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness + indexed chunk count |
| GET | `/api/config` | Pipeline switches/models from `.env` |
| POST | `/api/chat` | Full pipeline, streamed as Server-Sent Events (used by the UI) |
| POST | `/api/chat/complete` | Full pipeline, single JSON response (answer, sources, verification, stages) |
| GET | `/api/documents` | List indexed documents |
| POST | `/api/documents` | Upload + semantic-chunk + index a file (multipart `file`) |
| DELETE | `/api/documents/{doc_id}` | Remove a document |
| POST | `/api/tools/rag` | Run hybrid search + rerank only (`{"query": "..."}`) |
| POST | `/api/tools/web` | Run Tavily search only |

Request body for both chat endpoints: `{"message": "...", "history": [{"role": "user", "content": "..."}], "web_search": false}`
