# Multi-Agent RAG Chatbot

```
unsafe:            Memory → Planner → blocked
greeting:          Memory → Planner → Synthesizer
answer in memory:  Memory → Planner → Synthesizer          (no RAG / web / verifier)
search, web off:   Memory → Planner → RAG search → Verifier (question + chunks) → Synthesizer
search, web on:    Memory → Planner → Web search → Verifier (question + results) → Synthesizer
every answer:      → Memory save, in the background
```

| Component | Implementation |
|---|---|
| UI | React (Vite) — chat, live pipeline tracker, **Web search** toggle, document upload, sources & verification panel |
| Planner agent | Groq LLM: sees the recalled memories and decides unsafe / greeting / memory (the answer is already remembered) / search, and writes a standalone search query |
| RAG tool | Semantic chunking → ChromaDB (dense `bge-small` vectors) + in-memory BM25 keyword index → RRF hybrid fusion → `bge-reranker-v2-m3` cross-encoder rerank |
| Web search tool | Tavily — used instead of RAG when the UI **Web search** toggle is on |
| Verifier agent | Groq reasoning LLM (`VERIFIER_REASONING_EFFORT`): checks the question against the retrieved chunks (relevance, sufficiency, explicit content) and keeps only the relevant ones |
| Synthesizer agent | Groq reasoning LLM (`SYNTHESIZER_REASONING_EFFORT`): thinks, then writes the final answer from the verified chunks (streamed) |
| Long-term memory | [Supermemory](https://supermemory.ai): recalls facts about the user (profile + question-matched memories) before planning, saves each answered turn afterwards |

Everything (models, temperatures, switches, chunking, top-k, reranker, ChromaDB path/host, BM25 params, Tavily depth…) is set in `backend/.env` — see `backend/.env.example`.

## Setup

```bash
# backend
cd backend
cp .env.example .env          # add GROQ_API_KEY, TAVILY_API_KEY and (optional) SUPERMEMORY_API_KEY
uv pip install -r requirements.txt
../.venv/Scripts/python run.py      # uvicorn on HOST:PORT from .env; API docs at /docs

# frontend (new terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

First start downloads the embedding model (~70 MB) and the bge-reranker-v2-m3 int8 reranker (~570 MB) into `backend/data/models`.

## How a request flows (`backend/app/pipeline.py`)
1. **Memory recall** (`backend/app/memory.py`): fetches what Supermemory remembers about this user — their profile, memories matching the question, and the user's own words from matching saved conversations — and gives it to the agents as "what you remember about the user". Bounded by `MEMORY_TIMEOUT`; if Supermemory is slow or down, the request continues without memory.
2. **Planner** sees those memories and decides: unsafe → blocked; greeting → **Synthesizer**; **memory** — the remembered facts already answer it ("what's my name?") → straight to the **Synthesizer**, no RAG, web or verifier; or search, with a standalone query in which personal references are resolved from memory ("weather in my city" → "Kochi weather today").
3. **Search**: the knowledge base (semantic chunks → ChromaDB + BM25 → RRF → reranker), or **Tavily** when the UI's Web search toggle is on.
4. **Verifier** checks the question against the retrieved chunks: which are relevant, whether they're enough, and whether anything is explicit (→ blocked). Only relevant chunks continue.
5. **Synthesizer** thinks (`SYNTHESIZER_REASONING_EFFORT`), then writes the answer from those chunks, saying clearly what's missing if they weren't enough.
6. **Memory save**: the question and answer are appended (in the background) to one Supermemory document per conversation; Supermemory extracts the facts worth keeping. Blocked requests are never saved.

The verifier can be turned off with `ENABLE_VERIFIER=false`; RAG with `ENABLE_RAG=false`; memory with `ENABLE_MEMORY=false` (it is also off when no `SUPERMEMORY_API_KEY` / `SUPERMEMORY_BASE_URL` is set).

### Memory and user identity
Each browser gets an anonymous id (a UUID in `localStorage`) that scopes its memory to its own Supermemory namespace; **New chat** starts a new conversation id. This is not authentication — anyone who knows an id can read or erase that memory — so put real login in front of the API before exposing it publicly. Settings → Memory shows what is remembered and has a **Forget me** button.

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
| GET | `/api/memory` | What is remembered about the user (`X-User-Id` header) |
| DELETE | `/api/memory` | Forget everything about the user (`X-User-Id` header) |
| POST | `/api/tools/rag` | Run hybrid search + rerank only (`{"query": "..."}`) |
| POST | `/api/tools/web` | Run Tavily search only |

Request body for both chat endpoints: `{"message": "...", "history": [{"role": "user", "content": "..."}], "web_search": false, "user_id": "<uuid>", "conversation_id": "<uuid>"}` (`user_id` / `conversation_id` are optional; without `user_id` memory is skipped)
