"""Central configuration. Every knob of the pipeline is controlled from the environment / .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    # --- API keys ---
    groq_api_key: str = ""

    # --- LLM provider: "groq" (cloud) or "ollama" (local). Each agent can override it. ---
    llm_provider: str = "groq"
    planner_provider: str = ""              # empty = use llm_provider
    verifier_provider: str = ""
    synthesizer_provider: str = ""

    # --- Ollama (local models, OpenAI-compatible API) ---
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_planner_model: str = "qwen3:4b"
    ollama_verifier_model: str = "qwen3:8b"
    ollama_synthesizer_model: str = "qwen3:8b"
    ollama_timeout: float = 300.0           # local models can be slow on CPU
    ollama_reasoning_effort: str = "none"   # thinking models (qwen3): none = fastest | low | medium | high | "" = model default
    tavily_api_key: str = ""

    # --- Feature switches ---
    enable_rag: bool = True
    enable_web_search: bool = True          # if false, the UI web-search button is disabled
    enable_verifier: bool = True
    enable_reranker: bool = True

    # --- Planner agent (greeting or search? + search query) ---
    planner_model: str = "llama-3.3-70b-versatile"
    planner_temperature: float = 0.0
    enable_query_rewrite: bool = True       # search with the planner's standalone query (else the raw question)
    history_turns: int = 6                  # past messages sent to the agents for context

    # --- Verifier agent ---
    verifier_model: str = "openai/gpt-oss-120b"
    verifier_temperature: float = 0.0
    verifier_max_tokens: int = 4000         # includes the model's thinking tokens
    verifier_reasoning_effort: str = "high" # how hard the verifier thinks: low | medium | high | "" = model default
    verifier_min_confidence: float = 0.5    # below this the sources are treated as not enough to answer
    block_explicit_content: bool = True

    # --- Synthesizer agent ---
    synthesizer_model: str = "openai/gpt-oss-120b"
    synthesizer_temperature: float = 0.4
    synthesizer_max_tokens: int = 4000      # includes the model's thinking tokens
    synthesizer_reasoning_effort: str = "high"  # how hard it thinks before answering: low | medium | high | "" = default

    # --- Embeddings / reranker (fastembed, local ONNX) ---
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_model_file: str = "onnx/model_int8.onnx"  # custom rerankers only; onnx/model.onnx = full precision
    model_cache_dir: str = str(BACKEND_DIR / "data" / "models")

    # --- Semantic chunking ---
    chunk_breakpoint_percentile: float = 90.0   # higher = fewer, larger chunks
    chunk_buffer_size: int = 1                  # neighbouring sentences mixed into each sentence embedding
    chunk_min_chars: int = 200
    chunk_max_chars: int = 1800

    # --- Vector DB (ChromaDB) ---
    chroma_host: str = ""                       # empty => embedded persistent DB at chroma_path
    chroma_port: int = 8001
    chroma_path: str = str(BACKEND_DIR / "data" / "chroma")
    chroma_collection: str = "documents"

    # --- BM25 keyword index ---
    bm25_k1: float = 1.5                        # term-frequency saturation
    bm25_b: float = 0.75                        # document-length normalisation
    bm25_stemming: bool = True                  # "refunds" matches "refund"

    # --- Hybrid search + rerank ---
    dense_top_k: int = 20
    bm25_top_k: int = 20
    rrf_k: int = 60
    hybrid_candidates: int = 15                 # fused candidates passed to the reranker
    rerank_top_n: int = 5
    rerank_min_score: float = -8.0              # cross-encoder logits below this are dropped

    # --- Web search (Tavily) ---
    tavily_max_results: int = 5
    tavily_search_depth: str = "advanced"       # basic | advanced
    tavily_include_answer: bool = False

    # --- Long-term user memory (Supermemory) ---
    enable_memory: bool = True
    supermemory_api_key: str = ""
    supermemory_base_url: str = ""              # empty = Supermemory cloud; e.g. http://localhost:6767 when self-hosted
    memory_save_conversations: bool = True      # false = recall only, never write new memories
    memory_instant_extraction: bool = True      # extract facts from each turn right away (+1 billed op per turn)
    memory_max_items: int = 10                  # remembered facts passed to the agents
    memory_min_similarity: float = 0.5          # question-matched memories below this are ignored
    memory_timeout: float = 4.0                 # seconds; recall is skipped if Supermemory is slower

    # --- Server (uvicorn) ---
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    log_level: str = "info"
    cors_origins: str = "http://localhost:5173"
    max_upload_mb: int = 25

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def agent_llm(self, agent: str) -> tuple[str, str]:
        """(provider, model) for "planner", "verifier" or "synthesizer"."""
        provider = (getattr(self, f"{agent}_provider") or self.llm_provider).strip().lower()
        if provider == "ollama":
            return "ollama", getattr(self, f"ollama_{agent}_model")
        return "groq", getattr(self, f"{agent}_model")

    @property
    def uses_groq(self) -> bool:
        return any(self.agent_llm(a)[0] == "groq" for a in ("planner", "verifier", "synthesizer"))

    @property
    def web_search_available(self) -> bool:
        return self.enable_web_search and bool(self.tavily_api_key)

    @property
    def memory_available(self) -> bool:
        # The cloud needs an API key; a self-hosted server (SUPERMEMORY_BASE_URL) may not.
        return self.enable_memory and bool(self.supermemory_api_key or self.supermemory_base_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
