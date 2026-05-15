"""
Local text embeddings via sentence-transformers (no API key needed).
Model configured via .env: EMBED_MODEL (default: all-MiniLM-L6-v2).
Vectors cached on disk at seller_survival/data/mcat_embeddings.json.
"""
import json, os, math
from typing import Optional

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")

_CACHE_PATH = os.path.join(os.path.dirname(__file__), "data", "mcat_embeddings.json")

_cache: Optional[dict] = None
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def _load_cache() -> dict:
    global _cache
    if _cache is None:
        if os.path.exists(_CACHE_PATH):
            with open(_CACHE_PATH, encoding="utf-8") as f:
                _cache = json.load(f)
        else:
            _cache = {}
    return _cache


def _save_cache(cache: dict):
    os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def embed_batch(mcats: list[str]) -> dict[str, list[float]]:
    """Embed a list of mcat strings. Returns {mcat: vector}. Uses disk cache."""
    cache = _load_cache()
    missing = [m for m in mcats if m.lower() not in cache]
    if missing:
        model  = _get_model()
        keys   = [m.lower() for m in missing]
        vecs   = model.encode(keys, convert_to_numpy=True)
        for k, v in zip(keys, vecs):
            cache[k] = v.tolist()
        _save_cache(cache)
    return {m: cache[m.lower()] for m in mcats if m.lower() in cache}


def get_embedding(mcat: str) -> Optional[list[float]]:
    return embed_batch([mcat]).get(mcat)


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na  = math.sqrt(sum(x * x for x in a))
    nb  = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def max_pairwise_cosine(mcats_a: list[str], mcats_b: list[str]) -> float:
    """Max cosine similarity across all pairs of mcats between two sellers."""
    if not mcats_a or not mcats_b:
        return 0.0
    cache = _load_cache()
    vecs_a = [cache.get(m.lower()) for m in mcats_a if cache.get(m.lower())]
    vecs_b = [cache.get(m.lower()) for m in mcats_b if cache.get(m.lower())]
    if not vecs_a or not vecs_b:
        return 0.0
    best = 0.0
    for va in vecs_a:
        for vb in vecs_b:
            s = cosine(va, vb)
            if s > best:
                best = s
    return best
