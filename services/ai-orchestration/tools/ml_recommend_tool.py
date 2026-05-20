"""
ML recommendation tool — calls the existing CineScope ml-service (port 8000).
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

import httpx

_ML_URL = os.getenv("ML_SERVICE_URL", "http://localhost:8000")


async def ml_recommend(params: Dict[str, Any]) -> List[dict]:
    user_id = params.get("user_id") or params.get("userId")
    limit = int(params.get("limit", 20))

    if not user_id:
        return []

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"{_ML_URL}/recommend",
            json={"userId": str(user_id), "limit": limit},
        )
        r.raise_for_status()
        data = r.json()

    recs = data.get("recommendations", [])
    out = []
    for m in recs:
        score = m.get("score", 0)
        exp = m.get("explanation", {})
        out.append({
            "movie_id": m.get("movie_id"),
            "title": m.get("title", ""),
            "overview": m.get("overview", ""),
            "poster_path": m.get("poster_path"),
            "vote_average": m.get("vote_average", 0),
            "vote_count": m.get("vote_count", 0),
            "popularity": m.get("popularity", 0),
            "release_date": m.get("release_date", ""),
            "genre_ids": [],
            "genres": m.get("genres", []),
            "similarity_score": score,
            "explanation": exp.get("reason") if isinstance(exp, dict) else None,
        })
    return out
