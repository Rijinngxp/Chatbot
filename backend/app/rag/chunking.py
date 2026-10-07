"""Semantic chunking.

Text is split into sentences, each sentence is embedded together with its neighbours, and a chunk
boundary is placed wherever the cosine distance between consecutive sentences is above the
configured percentile. Chunks are then size-normalised (merged if too small, split if too large).
"""
import re

import numpy as np

from ..config import get_settings
from .models import dense_model
from .progress import Progress, no_progress

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])|\n{2,}")
EMBED_BATCH = 32


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text)
    parts = [p.strip() for p in _SENTENCE_RE.split(text)]
    return [p for p in parts if p]


def embed_with_progress(texts: list[str], stage: str, label: str, progress: Progress) -> np.ndarray:
    """Embed texts in batches, reporting progress after each batch."""
    total = len(texts)
    progress(stage, "running", f"0 / {total} {label}", 0.0)
    vectors = []
    for i, vec in enumerate(dense_model().embed(texts, batch_size=EMBED_BATCH), start=1):
        vectors.append(vec)
        if i % EMBED_BATCH == 0 or i == total:
            progress(stage, "running", f"{i} / {total} {label}", i / total)
    return np.array(vectors)


def semantic_chunks(text: str, progress: Progress = no_progress) -> list[str]:
    s = get_settings()
    sentences = split_sentences(text)
    progress("split", "done", f"{len(sentences):,} sentences")
    if len(sentences) <= 2:
        progress("embed_sentences", "skipped", "Too few sentences to compare")
        chunks = _enforce_sizes([" ".join(sentences)], s.chunk_min_chars, s.chunk_max_chars) if sentences else []
        progress("chunk", "done", f"{len(chunks)} chunk(s)")
        return chunks

    buf = s.chunk_buffer_size
    windows = [" ".join(sentences[max(0, i - buf) : i + buf + 1]) for i in range(len(sentences))]
    emb = embed_with_progress(windows, "embed_sentences", "sentences", progress)
    progress("embed_sentences", "done", f"{len(windows):,} sentence embeddings")

    progress("chunk", "running", "Finding topic breaks between sentences")
    emb /= np.linalg.norm(emb, axis=1, keepdims=True) + 1e-10
    distances = 1 - np.sum(emb[:-1] * emb[1:], axis=1)

    threshold = np.percentile(distances, s.chunk_breakpoint_percentile)
    breakpoints = {i for i, d in enumerate(distances) if d > threshold}

    chunks, current = [], []
    for i, sentence in enumerate(sentences):
        current.append(sentence)
        if i in breakpoints:
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))

    final = _enforce_sizes(chunks, s.chunk_min_chars, s.chunk_max_chars)
    avg = sum(len(c) for c in final) // max(len(final), 1)
    progress("chunk", "done", f"{len(final)} chunks · {len(breakpoints)} topic breaks · ~{avg:,} chars each")
    return final


def _enforce_sizes(chunks: list[str], min_chars: int, max_chars: int) -> list[str]:
    merged: list[str] = []
    for chunk in chunks:
        if merged and len(merged[-1]) < min_chars and len(merged[-1]) + len(chunk) <= max_chars:
            merged[-1] = f"{merged[-1]} {chunk}"
        else:
            merged.append(chunk)

    result: list[str] = []
    for chunk in merged:
        while len(chunk) > max_chars:
            cut = chunk.rfind(" ", 0, max_chars)
            cut = cut if cut > max_chars // 2 else max_chars
            result.append(chunk[:cut].strip())
            chunk = chunk[cut:].strip()
        if chunk:
            result.append(chunk)
    return result
