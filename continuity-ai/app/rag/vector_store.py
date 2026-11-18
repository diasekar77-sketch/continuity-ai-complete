from functools import lru_cache

import chromadb

from app.core.config import CHROMA_PATH
from app.rag.embeddings import get_embedder


class VectorStore:
    """Thin wrapper over ChromaDB. SQLite stays the source of truth; Chroma holds searchable copies."""

    def __init__(self, path: str = CHROMA_PATH, embedder=None):
        self.embedder = embedder or get_embedder()
        self.client = chromadb.PersistentClient(path=path)
        # Collection is keyed by embedder so switching models never mixes vector sizes.
        self.col = self.client.get_or_create_collection(
            f"policies_{self.embedder.name}", metadata={"hnsw:space": "cosine"})
        self.msg_col = self.client.get_or_create_collection(
            f"messages_{self.embedder.name}", metadata={"hnsw:space": "cosine"})

    def add_chunks(self, document_id: int, filename: str, category: str, chunks: list[dict]) -> int:
        if not chunks:
            return 0
        texts = [f"{c['section']}. {c['text']}" for c in chunks]
        self.col.add(
            ids=[f"{document_id}-{i}" for i in range(len(chunks))],
            embeddings=self.embedder.embed(texts), documents=[c["text"] for c in chunks],
            metadatas=[{"document_id": document_id, "filename": filename, "category": category or "",
                        "section": c["section"]} for c in chunks])
        return len(chunks)

    def delete_document(self, document_id: int) -> None:
        self.col.delete(where={"document_id": document_id})

    def query(self, text: str, k: int = 3, category: str | None = None) -> list[dict]:
        if self.col.count() == 0:
            return []
        res = self.col.query(query_embeddings=self.embedder.embed([text]), n_results=min(k, self.col.count()),
                             where={"category": category} if category else None)
        return [{"text": d, "score": round(1 - dist, 3), **m}
                for d, m, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])]


    # ---- conversation memory: searchable copies of transcript messages (SQLite remains the record) ----
    def upsert_messages(self, case_id: int, messages: list[dict]) -> None:
        if not messages:
            return
        self.msg_col.upsert(
            ids=[f"m{m['message_id']}" for m in messages],
            embeddings=self.embedder.embed([f"{m['speaker']}: {m['content']}" for m in messages]),
            documents=[m["content"] for m in messages],
            metadatas=[{"case_id": case_id, "message_id": m["message_id"], "speaker": m["speaker"]} for m in messages])

    def query_messages(self, text: str, case_id: int, k: int = 4) -> list[dict]:
        n = len(self.msg_col.get(where={"case_id": case_id})["ids"])
        if n == 0:
            return []
        res = self.msg_col.query(query_embeddings=self.embedder.embed([text]), n_results=min(k, n),
                                 where={"case_id": case_id})
        return [{"message_id": m["message_id"], "score": round(1 - d, 3)}
                for m, d in zip(res["metadatas"][0], res["distances"][0])]


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    return VectorStore()
