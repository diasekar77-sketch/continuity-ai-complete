"""Embedders. Both expose .embed(texts) -> list[list[float]], .name and .min_score
(the similarity below which we treat a policy hit as 'not found')."""
import math
import re
import zlib

from app.core import config

_STOP = set("a an the and or of to in on for is are was be by with as at it this that from if you your we our "
            "must may can not no do does should will".split())


class HashEmbedder:
    """Dependency-free lexical embedder (hashed bag of words). Used for tests and when the
    sentence-transformers model cannot be downloaded. Weaker than a neural model, but deterministic."""
    name, dim, min_score = "hash", 1024, 0.12

    def embed(self, texts):
        out = []
        for t in texts:
            v = [0.0] * self.dim
            for w in re.findall(r"[a-z0-9]+", t.lower()):
                if w in _STOP:
                    continue
                w = w[:-1] if len(w) > 3 and w.endswith("s") else w
                v[zlib.crc32(w.encode()) % self.dim] += 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out


class SentenceTransformerEmbedder:
    name, min_score = "minilm", 0.25

    def __init__(self, model="all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model)

    def embed(self, texts):
        return self.model.encode(list(texts), normalize_embeddings=True).tolist()


_cached = None


def get_embedder():
    global _cached
    if _cached is not None:
        return _cached
    emb = None
    if config.EMBEDDER in ("auto", "sentence-transformers"):
        try:
            emb = SentenceTransformerEmbedder()
        except Exception as e:  # noqa: BLE001
            if config.EMBEDDER == "sentence-transformers":
                raise
            print(f"[ContinuityAI] sentence-transformers unavailable ({type(e).__name__}); using hash embedder")
    emb = emb or HashEmbedder()
    if config.POLICY_MIN_SCORE:
        emb.min_score = float(config.POLICY_MIN_SCORE)
    _cached = emb
    return emb
