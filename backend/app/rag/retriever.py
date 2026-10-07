"""Retrieval over the spec: ChromaDB + sentence-transformers embeddings, with a dependency-free lexical fallback."""
from __future__ import annotations

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass

log = logging.getLogger("uds.rag")
STOP = {"the", "is", "an", "of", "to", "and", "or", "in", "on", "for", "it", "do", "does", "how", "what", "which", "can", "are", "with", "by", "be", "if", "me", "my", "i", "when", "a"}


@dataclass(frozen=True)
class Chunk:
    id: str
    title: str
    text: str
    source: str = "spec"


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


def tokens(text: str) -> list:
    return [t for t in re.findall(r"[a-z0-9§]+", text.lower().replace("0x", "")) if t not in STOP and len(t) > 1]


class LexicalRetriever:
    mode = "lexical"

    def __init__(self):
        self.chunks: dict = {}

    def add(self, chunks: list) -> None:
        for c in chunks:
            self.chunks[c.id] = c

    def search(self, query: str, k: int = 3) -> list:
        q = set(tokens(query))
        if not q or not self.chunks:
            return []
        docs = {cid: Counter(tokens(c.title + " " + c.text)) for cid, c in self.chunks.items()}
        n = len(docs)
        idf = {t: math.log(1 + n / (1 + sum(1 for d in docs.values() if t in d))) for t in q}
        scored = []
        for cid, tf in docs.items():
            s = sum(idf[t] * (1 + math.log(tf[t])) for t in q if tf[t])
            if s > 0:
                scored.append(Hit(self.chunks[cid], round(s, 3)))
        return sorted(scored, key=lambda h: -h.score)[:k]


class ChromaRetriever:
    mode = "vector"

    def __init__(self, persist_dir: str, model_name: str, collection: str = "uds_spec"):
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

        self.prefix = "Represent this sentence for searching relevant passages: " if "bge" in model_name.lower() else ""
        client = chromadb.PersistentClient(path=persist_dir)
        self.col = client.get_or_create_collection(
            collection, embedding_function=SentenceTransformerEmbeddingFunction(model_name=model_name), metadata={"hnsw:space": "cosine"})

    def add(self, chunks: list) -> None:
        if chunks:
            self.col.upsert(ids=[c.id for c in chunks], documents=[f"{c.title}\n{c.text}" for c in chunks],
                            metadatas=[{"title": c.title, "text": c.text, "source": c.source} for c in chunks])

    def search(self, query: str, k: int = 3) -> list:
        n = self.col.count()
        if not query.strip() or n == 0:
            return []
        r = self.col.query(query_texts=[self.prefix + query], n_results=min(k, n))
        return [Hit(Chunk(i, m["title"], m["text"], m["source"]), round(1 - d, 3))
                for i, m, d in zip(r["ids"][0], r["metadatas"][0], r["distances"][0])]


def build_retriever(mode: str, chroma_dir: str, model: str):
    if mode == "vector":
        try:
            return ChromaRetriever(chroma_dir, model)
        except Exception as exc:  # missing optional deps, offline model download, corrupt store
            log.warning("Vector retrieval unavailable (%s); using lexical fallback", exc)
    return LexicalRetriever()


def chunk_document(name: str, text: str, max_chars: int = 900) -> list:
    """Split plain text / markdown into heading-aware chunks."""
    sections, title, buf = [], name, []
    for line in text.splitlines():
        if re.match(r"^#{1,4}\s+\S", line):
            if buf:
                sections.append((title, "\n".join(buf)))
            title, buf = line.lstrip("# ").strip(), []
        else:
            buf.append(line)
    sections.append((title, "\n".join(buf)))
    chunks = []
    for title, body in sections:
        paras, cur = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()], ""
        parts = []
        for p in paras:
            if cur and len(cur) + len(p) > max_chars:
                parts.append(cur)
                cur = ""
            cur = f"{cur}\n\n{p}".strip()
        if cur:
            parts.append(cur)
        for part in parts:
            chunks.append(Chunk(f"{name}#{len(chunks) + 1}", title, part[: max_chars * 2], source=name))
    return chunks
