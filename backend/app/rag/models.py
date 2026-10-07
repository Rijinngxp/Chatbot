"""Lazy-loaded fastembed models (dense embedder and cross-encoder reranker)."""
import threading
from functools import lru_cache

from fastembed import TextEmbedding
from fastembed.common.model_description import ModelSource
from fastembed.rerank.cross_encoder import TextCrossEncoder

from ..config import get_settings

_lock = threading.Lock()

# Rerankers fastembed doesn't ship, mapped to a Hugging Face repo with ONNX weights.
CUSTOM_RERANKERS = {
    "BAAI/bge-reranker-v2-m3": "onnx-community/bge-reranker-v2-m3-ONNX",
}


@lru_cache
def dense_model() -> TextEmbedding:
    s = get_settings()
    with _lock:
        return TextEmbedding(s.embedding_model, cache_dir=s.model_cache_dir)


@lru_cache
def reranker() -> TextCrossEncoder:
    s = get_settings()
    name = s.reranker_model
    with _lock:
        if name not in {m["model"] for m in TextCrossEncoder.list_supported_models()}:
            # Full-precision ONNX exports keep their weights in a separate "<file>_data" file.
            extra = [f"{s.reranker_model_file}_data"] if s.reranker_model_file.endswith("/model.onnx") else None
            TextCrossEncoder.add_custom_model(
                model=name,
                sources=ModelSource(hf=CUSTOM_RERANKERS.get(name, name)),
                model_file=s.reranker_model_file,
                additional_files=extra,
            )
        return TextCrossEncoder(name, cache_dir=s.model_cache_dir)
