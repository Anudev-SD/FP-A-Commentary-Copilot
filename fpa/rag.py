"""RAG over the finance glossary and reporting notes.

Chunks are split by '## ' heading. Chunk ids look like 'glossary#gross-margin-percent' and
are what the model cites, e.g. [D:glossary#gross-margin-percent].

Two backends:
  chroma : ChromaDB + OpenAI embeddings (the real thing)
  tfidf  : local keyword search, free and offline (used for tests / dry runs)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import config


@dataclass
class Chunk:
    id: str
    title: str
    text: str
    source: str
    pinned: bool


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def load_chunks(docs_dir: Path | None = None) -> list[Chunk]:
    docs_dir = docs_dir or config.DOCS_DIR
    chunks = []
    for path in sorted(docs_dir.glob("*.md")):
        parts = re.split(r"(?m)^## ", path.read_text(encoding="utf-8"))
        for part in parts[1:]:
            title, _, body = part.partition("\n")
            title = title.strip()
            pinned = "<!-- pin -->" in body
            body = body.replace("<!-- pin -->", "").strip()
            chunks.append(Chunk(f"{path.stem}#{slugify(title)}", title, f"{title}\n{body}", path.name, pinned))
    return chunks


class TfidfBackend:
    name = "tfidf"

    def __init__(self, chunks):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.chunks = chunks
        self.vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.matrix = self.vec.fit_transform([c.text for c in chunks])

    def search(self, query: str, k: int):
        sims = (self.matrix @ self.vec.transform([query]).T).toarray().ravel()
        order = sims.argsort()[::-1][:k]
        return [(self.chunks[i], float(sims[i])) for i in order if sims[i] > 0]


class ChromaBackend:
    name = "chroma"

    def __init__(self, chunks):
        import chromadb
        from chromadb.utils import embedding_functions
        ef = embedding_functions.OpenAIEmbeddingFunction(api_key=config.OPENAI_API_KEY, model_name=config.EMBED_MODEL)
        client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        self.col = client.get_or_create_collection("fpa_docs", embedding_function=ef, metadata={"hnsw:space": "cosine"})
        self.by_id = {c.id: c for c in chunks}
        stale = [i for i in self.col.get()["ids"] if i not in self.by_id]
        if stale:
            self.col.delete(ids=stale)
        self.col.upsert(ids=[c.id for c in chunks], documents=[c.text for c in chunks],
                        metadatas=[{"source": c.source, "title": c.title} for c in chunks])

    def search(self, query: str, k: int):
        res = self.col.query(query_texts=[query], n_results=min(k, len(self.by_id)))
        return [(self.by_id[i], 1.0 - d) for i, d in zip(res["ids"][0], res["distances"][0]) if i in self.by_id]


class DocIndex:
    def __init__(self, backend: str = "auto", docs_dir: Path | None = None):
        self.chunks = load_chunks(docs_dir)
        self.by_id = {c.id: c for c in self.chunks}
        self.ids = set(self.by_id)
        if backend == "auto":
            backend = "chroma" if config.OPENAI_API_KEY else "tfidf"
        self.backend = ChromaBackend(self.chunks) if backend == "chroma" else TfidfBackend(self.chunks)
        self.backend_name = self.backend.name

    def retrieve(self, queries: list[str], k_per_query: int = 2, max_chunks: int = 10) -> list[Chunk]:
        """Pinned chunks first (rules that must always apply), then semantic hits."""
        picked = {c.id: c for c in self.chunks if c.pinned}
        for q in queries:
            for chunk, _score in self.backend.search(q, k_per_query):
                if len(picked) >= max_chunks:
                    break
                picked.setdefault(chunk.id, chunk)
        return list(picked.values())
