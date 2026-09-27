"""Retrieval: keyword (BM25), dense (two embedding models, stored in Qdrant) and hybrid (reciprocal rank fusion).

Financial questions mix exact terms ("Finance costs", "Fiscal 2026") with paraphrase ("how much did it borrow?").
BM25 catches the first, embeddings the second; hybrid fuses both. Which works best is measured, not assumed:
see evals/retrieval.py.

    python -m redflag.index            # embeds all chunks with MiniLM (local)
    python -m redflag.index minilm gemini
                                       # Gemini embeddings via API (slower on the free tier)
"""

import atexit
import shutil
import sys
import tempfile
import threading
from pathlib import Path
import time
from functools import lru_cache

import numpy as np
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document as LCDocument
from qdrant_client import QdrantClient, models

from redflag.config import DOCS, EMBEDDERS, INDEX
from redflag.ingest import load_chunks

GEMINI_DIMS = 768


@lru_cache
def _local_model(name: str):
    from fastembed import TextEmbedding

    return TextEmbedding(EMBEDDERS[name])


def _embed_local(name: str):
    return lambda texts, **_: np.array(list(_local_model(name).embed(texts, batch_size=64)))


def _embed_gemini(texts: list[str], task: str = "RETRIEVAL_DOCUMENT") -> np.ndarray:
    import litellm

    out = []
    for i in range(0, len(texts), 50):
        batch = texts[i:i + 50]
        if i and i % 500 == 0:
            print(f"  gemini embedded {i}/{len(texts)}", flush=True)
        for attempt in range(8):
            try:
                r = litellm.embedding(model=EMBEDDERS["gemini"], input=batch, dimensions=GEMINI_DIMS, task_type=task)
                out += [d["embedding"] for d in r.data]
                break
            except Exception as e:  # free tier: 429s are expected; back off and retry
                if attempt == 7:
                    raise
                time.sleep(min(60, 5 * 2 ** attempt))
                print(f"  gemini embed batch {i}: retry {attempt + 1} ({type(e).__name__})", flush=True)
    return np.array(out)


EMBED = {"minilm": _embed_local("minilm"), "bge": _embed_local("bge"), "gemini": _embed_gemini}


_OPEN = threading.Lock()


def client(embedder: str = "minilm") -> QdrantClient:
    with _OPEN:  # the memo's section agents run in parallel threads; open each store only once
        return _client(embedder)


@lru_cache
def _client(embedder: str) -> QdrantClient:
    """One local Qdrant store per embedder (local mode allows one process per store, so a slow rebuild of one
    never blocks queries on the other)."""
    INDEX.mkdir(parents=True, exist_ok=True)
    path = INDEX / f"qdrant_{embedder}"
    try:
        q = QdrantClient(path=str(path))
    except RuntimeError as e:
        # Qdrant local mode allows one process per store. Queries only read it, so when another process (the web app,
        # the API, an eval) holds the lock, open a private snapshot copy instead of failing.
        if "already accessed" not in str(e):
            raise
        snap = Path(tempfile.mkdtemp(prefix=f"qdrant_{embedder}_"))
        shutil.copytree(path, snap, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.lock"))
        q = QdrantClient(path=str(snap))
    atexit.register(q.close)
    return q


def build_dense(embedder: str) -> int:
    chunks = load_chunks()
    vectors = EMBED[embedder]([c["text"] for c in chunks])
    q = client(embedder)
    name = f"chunks_{embedder}"
    if q.collection_exists(name):
        q.delete_collection(name)
    q.create_collection(name, vectors_config=models.VectorParams(size=vectors.shape[1], distance=models.Distance.COSINE))
    q.upload_points(name, [models.PointStruct(id=i, vector=v.tolist(), payload=c) for i, (c, v) in enumerate(zip(chunks, vectors))])
    return len(chunks)


def dense_search(query: str, doc: str, embedder: str = "minilm", k: int = 8) -> list[dict]:
    qv = EMBED[embedder]([query], **({"task": "RETRIEVAL_QUERY"} if embedder == "gemini" else {}))[0]
    hits = client(embedder).query_points(f"chunks_{embedder}", query=qv.tolist(), limit=k,
                                 query_filter=models.Filter(must=[models.FieldCondition(key="doc", match=models.MatchValue(value=doc))])).points
    return [h.payload for h in hits]


@lru_cache
def _bm25(doc: str) -> BM25Retriever:
    docs = [LCDocument(page_content=c["text"], metadata=c) for c in load_chunks(doc)]
    return BM25Retriever.from_documents(docs, k=50)


def bm25_search(query: str, doc: str, k: int = 8) -> list[dict]:
    r = _bm25(doc)
    return [d.metadata for d in r.invoke(query)[:k]]


def rrf(rankings: list[list[dict]], k: int = 8, c: int = 60) -> list[dict]:
    """Reciprocal rank fusion: robust to the two retrievers' scores being on different scales."""
    score, by_id = {}, {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking):
            score[hit["id"]] = score.get(hit["id"], 0) + 1 / (c + rank + 1)
            by_id[hit["id"]] = hit
    return [by_id[i] for i in sorted(score, key=score.get, reverse=True)[:k]]


def search(query: str, doc: str, mode: str = "hybrid", k: int = 8, embedder: str = "minilm") -> list[dict]:
    if mode == "bm25":
        return bm25_search(query, doc, k)
    if mode == "dense":
        return dense_search(query, doc, embedder, k)
    return rrf([bm25_search(query, doc, 30), dense_search(query, doc, embedder, 30)], k)


if __name__ == "__main__":
    for e in sys.argv[1:] or ["minilm"]:
        t = time.time()
        print(e, build_dense(e), "chunks", f"{time.time() - t:.0f}s")
    print({d: len(load_chunks(d)) for d in DOCS})
