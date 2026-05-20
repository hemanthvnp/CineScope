"""
TMDB tool — search, discover, movie details, trending, TMDB-native similarity.
All functions share a single httpx.AsyncClient kept alive for the process.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx

_BASE = "https://api.themoviedb.org/3"
_KEY = os.getenv("TMDB_API_KEY", "")

# Shared client — created lazily, reused across calls
_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=_BASE,
            timeout=8.0,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
    return _client


def _norm(movie: dict) -> dict:
    """Normalise a TMDB movie object to the shape every tool returns."""
    return {
        "movie_id": movie.get("id"),
        "title": movie.get("title", ""),
        "overview": movie.get("overview", ""),
        "poster_path": movie.get("poster_path"),
        "vote_average": movie.get("vote_average", 0),
        "vote_count": movie.get("vote_count", 0),
        "popularity": movie.get("popularity", 0),
        "release_date": movie.get("release_date", ""),
        "genre_ids": movie.get("genre_ids", []),
        "original_language": movie.get("original_language", "en"),
    }


# ── Tool functions (each receives a `params` dict from the execution engine) ──

async def tmdb_search(params: Dict[str, Any]) -> List[dict]:
    query = params.get("query", "")
    limit = int(params.get("limit", 10))
    year = params.get("year")
    if not query:
        return []

    p: dict = {"api_key": _KEY, "query": query, "page": 1, "include_adult": False}
    if year:
        p["year"] = year

    r = await _get_client().get("/search/movie", params=p)
    r.raise_for_status()
    results = r.json().get("results", [])

    # Client-side genre filter
    genre_name = (params.get("genre") or "").lower()
    if genre_name:
        results = [m for m in results if genre_name in (m.get("original_title", "") + " " + str(m.get("genre_ids", []))).lower()]

    return [_norm(m) for m in results[:limit]]


async def tmdb_discover(params: Dict[str, Any]) -> List[dict]:
    limit = int(params.get("limit", 20))
    p: dict = {
        "api_key": _KEY,
        "sort_by": "popularity.desc",
        "vote_count.gte": 50,
        "page": 1,
    }

    genres: List[str] = params.get("genres", []) or []
    if genres:
        # TMDB needs genre IDs; map common genre names
        genre_id_map = {
            "action": 28, "adventure": 12, "animation": 16, "comedy": 35,
            "crime": 80, "documentary": 99, "drama": 18, "family": 10751,
            "fantasy": 14, "history": 36, "horror": 27, "music": 10402,
            "mystery": 9648, "romance": 10749, "sci-fi": 878, "science fiction": 878,
            "thriller": 53, "war": 10752, "western": 37,
        }
        ids = [genre_id_map[g.lower()] for g in genres if g.lower() in genre_id_map]
        if ids:
            p["with_genres"] = ",".join(map(str, ids))

    if params.get("year_from"):
        p["primary_release_date.gte"] = f"{params['year_from']}-01-01"
    if params.get("year_to"):
        p["primary_release_date.lte"] = f"{params['year_to']}-12-31"
    if params.get("language"):
        p["with_original_language"] = params["language"]

    r = await _get_client().get("/discover/movie", params=p)
    r.raise_for_status()
    return [_norm(m) for m in r.json().get("results", [])[:limit]]


async def tmdb_trending(params: Dict[str, Any]) -> List[dict]:
    limit = int(params.get("limit", 20))
    r = await _get_client().get("/trending/movie/week", params={"api_key": _KEY})
    r.raise_for_status()
    return [_norm(m) for m in r.json().get("results", [])[:limit]]


async def tmdb_movie_details(params: Dict[str, Any]) -> Optional[dict]:
    """Fetch full movie details. Resolves movie_id from deps if not in params."""
    movie_id = params.get("movie_id")

    # Resolve from resolve_seed dependency
    dep = params.get("_dep_resolve_seed") or params.get("_dep_resolve_movie")
    if not movie_id and dep:
        if isinstance(dep, list) and dep:
            movie_id = dep[0].get("movie_id")
        elif isinstance(dep, dict):
            movie_id = dep.get("movie_id")

    if not movie_id:
        return None

    r = await _get_client().get(
        f"/movie/{movie_id}",
        params={"api_key": _KEY, "append_to_response": "credits,keywords"},
    )
    r.raise_for_status()
    data = r.json()
    genres = [g["name"] for g in data.get("genres", [])]
    cast = [c["name"] for c in data.get("credits", {}).get("cast", [])[:5]]

    return {
        **_norm(data),
        "genres": genres,
        "runtime": data.get("runtime"),
        "tagline": data.get("tagline", ""),
        "cast": cast,
        "budget": data.get("budget"),
        "revenue": data.get("revenue"),
        "imdb_id": data.get("imdb_id"),
    }


async def tmdb_similar(params: Dict[str, Any]) -> List[dict]:
    """TMDB's own similarity endpoint for a seed movie."""
    movie_id = params.get("movie_id")
    limit = int(params.get("limit", 20))

    dep = params.get("_dep_resolve_seed")
    if not movie_id and dep:
        if isinstance(dep, list) and dep:
            movie_id = dep[0].get("movie_id")
        elif isinstance(dep, dict):
            movie_id = dep.get("movie_id")

    if not movie_id:
        return []

    r = await _get_client().get(
        f"/movie/{movie_id}/similar",
        params={"api_key": _KEY, "page": 1},
    )
    r.raise_for_status()
    results = r.json().get("results", [])
    for m in results:
        m["similarity_score"] = round(0.5 + m.get("vote_average", 0) / 20, 3)
    return [_norm(m) | {"similarity_score": m["similarity_score"]} for m in results[:limit]]
