"""
Semantic search — in-process vector index built from TMDB popular movies.

Uses sentence-transformers (all-MiniLM-L6-v2) if available.
Falls back to sklearn TF-IDF cosine similarity when the library is absent.

The corpus is fetched once at startup via _ensure_initialized().
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional

import httpx
import numpy as np

_TMDB_KEY = os.getenv("TMDB_API_KEY", "")
_TMDB_BASE = "https://api.themoviedb.org/3"

# Lazy state
_corpus: List[dict] = []
_matrix: Optional[np.ndarray] = None   # (n_movies, dim) normalised embeddings
_use_sbert = False
_model: Any = None
_vectorizer: Any = None                 # TF-IDF fallback
_init_lock = asyncio.Lock()
_initialized = False


async def _ensure_initialized() -> None:
    global _initialized
    if _initialized:
        return
    async with _init_lock:
        if _initialized:
            return
        await _build_index()
        _initialized = True


async def _fetch_corpus() -> List[dict]:
    movies: dict[int, dict] = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = [
            client.get(f"{_TMDB_BASE}/movie/popular", params={"api_key": _TMDB_KEY, "page": p})
            for p in range(1, 6)
        ] + [
            client.get(f"{_TMDB_BASE}/trending/movie/week", params={"api_key": _TMDB_KEY}),
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for r in responses:
            if isinstance(r, Exception):
                continue
            for m in r.json().get("results", []):
                if m.get("id") and m.get("title"):
                    movies[m["id"]] = m
    return list(movies.values())


def _make_doc(movie: dict) -> str:
    title = movie.get("title", "")
    overview = movie.get("overview", "")
    year = str(movie.get("release_date", ""))[:4]
    genre_ids = movie.get("genre_ids", [])
    return f"{title} {overview} {year} genres {' '.join(map(str, genre_ids))}"


async def _build_index() -> None:
    global _corpus, _matrix, _use_sbert, _model, _vectorizer

    print("[semantic_search] Building movie index…")
    _corpus = await _fetch_corpus()
    if not _corpus:
        print("[semantic_search] WARNING: empty corpus, semantic search will return nothing")
        return

    docs = [_make_doc(m) for m in _corpus]

    # Try sentence-transformers first
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        emb = _model.encode(docs, normalize_embeddings=True, show_progress_bar=False)
        _matrix = emb.astype(np.float32)
        _use_sbert = True
        print(f"[semantic_search] SBERT index: {len(_corpus)} movies, dim={_matrix.shape[1]}")
        return
    except Exception:
        pass

    # Fallback: TF-IDF
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
    from sklearn.preprocessing import normalize  # type: ignore

    _vectorizer = TfidfVectorizer(max_features=8000, ngram_range=(1, 2), stop_words="english")
    mat = _vectorizer.fit_transform(docs).toarray().astype(np.float32)
    _matrix = normalize(mat)
    print(f"[semantic_search] TF-IDF index: {len(_corpus)} movies, features={_matrix.shape[1]}")


def _encode_query(query: str) -> np.ndarray:
    if _use_sbert and _model is not None:
        return _model.encode([query], normalize_embeddings=True)[0].astype(np.float32)
    # TF-IDF
    from sklearn.preprocessing import normalize  # type: ignore
    vec = _vectorizer.transform([query]).toarray().astype(np.float32)
    return normalize(vec)[0]


async def semantic_search(params: Dict[str, Any]) -> List[dict]:
    await _ensure_initialized()

    query = str(params.get("query", ""))
    k = int(params.get("k", 20))

    if _matrix is None or not _corpus or not query:
        return []

    q_vec = _encode_query(query)
    scores = _matrix @ q_vec                        # cosine (vectors are normalised)

    top_idx = int(min(k, len(_corpus)))
    indices = np.argpartition(scores, -top_idx)[-top_idx:]
    indices = indices[np.argsort(scores[indices])[::-1]]

    results = []
    for idx in indices:
        m = dict(_corpus[idx])
        m["movie_id"] = m.pop("id", m.get("movie_id"))
        m["similarity_score"] = round(float(scores[idx]), 4)
        results.append(m)

    return results
