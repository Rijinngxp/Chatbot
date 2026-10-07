"""ChromaDB vector store + BM25 keyword index, fused with RRF and reranked by a cross-encoder."""
import threading
import uuid
from datetime import datetime, timezone

import chromadb

from ..config import get_settings
from .bm25 import BM25Index
from .chunking import embed_with_progress, semantic_chunks
from .models import dense_model, reranker
from .progress import Progress, no_progress

ADD_BATCH = 500


class VectorStore:
    def __init__(self) -> None:
        s = get_settings()
        self.client = (
            chromadb.HttpClient(host=s.chroma_host, port=s.chroma_port)
            if s.chroma_host
            else chromadb.PersistentClient(path=s.chroma_path)
        )
        self.collection = self.client.get_or_create_collection(
            s.chroma_collection,
            embedding_function=None,  # we supply our own fastembed vectors
            configuration={"hnsw": {"space": "cosine"}},
        )
        self._lock = threading.Lock()
        self.bm25 = BM25Index(k1=s.bm25_k1, b=s.bm25_b, stem=s.bm25_stemming)
        self._chunks: list[dict] = []  # BM25 doc_idx -> {"id", "text", "meta"}
        self._rebuild_bm25()

    # ---------- BM25 index (rebuilt from Chroma, the source of truth) ----------
    def _rebuild_bm25(self) -> None:
        chunks, offset = [], 0
        while True:
            page = self.collection.get(include=["documents", "metadatas"], limit=1000, offset=offset)
            chunks += [
                {"id": i, "text": d, "meta": m} for i, d, m in zip(page["ids"], page["documents"], page["metadatas"])
            ]
            if len(page["ids"]) < 1000:
                break
            offset += 1000
        index = BM25Index(k1=self.bm25.k1, b=self.bm25.b, stem=self.bm25.stem)
        index.build([c["text"] for c in chunks])
        self.bm25, self._chunks = index, chunks

    # ---------- ingestion ----------
    def add_document(self, text: str, filename: str, progress: Progress = no_progress) -> dict:
        chunks = semantic_chunks(text, progress)
        if not chunks:
            raise ValueError("No text could be extracted from the document")

        doc_id = str(uuid.uuid4())
        uploaded_at = datetime.now(timezone.utc).isoformat()
        vectors = embed_with_progress(chunks, "embed_chunks", "chunks", progress)
        embeddings = [v.tolist() for v in vectors]
        progress("embed_chunks", "done", f"{len(chunks)} vectors · {len(embeddings[0])} dimensions")

        metadatas = [
            {"doc_id": doc_id, "filename": filename, "chunk_index": i, "uploaded_at": uploaded_at}
            for i in range(len(chunks))
        ]
        ids = [str(uuid.uuid4()) for _ in chunks]
        with self._lock:
            progress("store", "running", "Saving chunks and vectors to ChromaDB")
            for start in range(0, len(chunks), ADD_BATCH):
                end = start + ADD_BATCH
                self.collection.add(
                    ids=ids[start:end],
                    embeddings=embeddings[start:end],
                    documents=chunks[start:end],
                    metadatas=metadatas[start:end],
                )
            progress("store", "done", f"{len(chunks)} chunks saved to '{self.collection.name}'")
            progress("index", "running", "Rebuilding the BM25 keyword index")
            self._rebuild_bm25()
            progress("index", "done", f"{self.bm25.n_docs:,} chunks · {len(self.bm25.postings):,} terms indexed")
        return {"doc_id": doc_id, "filename": filename, "chunks": len(chunks), "uploaded_at": uploaded_at}

    def list_documents(self) -> list[dict]:
        docs: dict[str, dict] = {}
        for c in self._chunks:
            m = c["meta"]
            d = docs.setdefault(
                m["doc_id"],
                {"doc_id": m["doc_id"], "filename": m["filename"], "uploaded_at": m["uploaded_at"], "chunks": 0},
            )
            d["chunks"] += 1
        return sorted(docs.values(), key=lambda d: d["uploaded_at"], reverse=True)

    def delete_document(self, doc_id: str) -> None:
        with self._lock:
            self.collection.delete(where={"doc_id": doc_id})
            self._rebuild_bm25()

    def count(self) -> int:
        return self.collection.count()

    # ---------- retrieval ----------
    def hybrid_search(self, query: str) -> list[dict]:
        s = get_settings()
        total = self.collection.count()
        if total == 0:
            return []

        # Dense (semantic) search in Chroma
        qd = next(iter(dense_model().query_embed(query))).tolist()
        dense = self.collection.query(
            query_embeddings=[qd], n_results=min(s.dense_top_k, total), include=["documents", "metadatas"]
        )
        dense_hits = [
            {"id": i, "text": d, "meta": m}
            for i, d, m in zip(dense["ids"][0], dense["documents"][0], dense["metadatas"][0])
        ]

        # BM25 (keyword) search
        bm25, chunks = self.bm25, self._chunks  # snapshot in case a rebuild swaps them
        bm25_hits = [chunks[idx] | {"bm25_score": score} for idx, score in bm25.search(query, s.bm25_top_k)]

        # Reciprocal Rank Fusion
        fused: dict[str, dict] = {}
        for hits, label in ((dense_hits, "dense"), (bm25_hits, "bm25")):
            for rank, hit in enumerate(hits):
                entry = fused.setdefault(hit["id"], {"hit": hit, "rrf": 0.0, "matched_by": []})
                entry["rrf"] += 1.0 / (s.rrf_k + rank + 1)
                entry["matched_by"].append(label)

        candidates = sorted(fused.values(), key=lambda e: e["rrf"], reverse=True)[: s.hybrid_candidates]
        results = [
            {
                "text": c["hit"]["text"],
                "filename": c["hit"]["meta"]["filename"],
                "chunk_index": c["hit"]["meta"]["chunk_index"],
                "rrf_score": round(c["rrf"], 5),
                "matched_by": c["matched_by"],
            }
            for c in candidates
        ]

        if s.enable_reranker and results:
            scores = list(reranker().rerank(query, [r["text"] for r in results]))
            for r, score in zip(results, scores):
                r["rerank_score"] = round(float(score), 4)
            results = [r for r in results if r["rerank_score"] >= s.rerank_min_score]
            results.sort(key=lambda r: r["rerank_score"], reverse=True)

        return results[: s.rerank_top_n]


_store: VectorStore | None = None
_store_lock = threading.Lock()


def get_store() -> VectorStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = VectorStore()
    return _store
