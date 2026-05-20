"""
Reviews tool — fetches TMDB reviews for a movie.
The aggregator / synthesizer handles summarisation via Claude if requested.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx

_TMDB_KEY = os.getenv("TMDB_API_KEY", "")
_TMDB_BASE = "https://api.themoviedb.org/3"


async def movie_reviews(params: Dict[str, Any]) -> Optional[dict]:
    movie_id = params.get("movie_id")

    # Resolve from dep
    dep = params.get("_dep_resolve_movie") or params.get("_dep_resolve_seed")
    if not movie_id and dep:
        if isinstance(dep, list) and dep:
            movie_id = dep[0].get("movie_id")
        elif isinstance(dep, dict):
            movie_id = dep.get("movie_id")

    if not movie_id:
        return None

    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.get(
            f"{_TMDB_BASE}/movie/{movie_id}/reviews",
            params={"api_key": _TMDB_KEY, "page": 1},
        )
        r.raise_for_status()
        raw = r.json().get("results", [])

    reviews: List[dict] = [
        {
            "author": rev.get("author", "Anonymous"),
            "rating": rev.get("author_details", {}).get("rating"),
            "content": (rev.get("content", ""))[:600],
        }
        for rev in raw[:8]
        if rev.get("content")
    ]

    return {
        "movie_id": movie_id,
        "total_reviews": r.json().get("total_results", len(reviews)),
        "reviews": reviews,
    }
