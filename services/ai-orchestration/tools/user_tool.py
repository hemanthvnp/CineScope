"""
User tool — fetches profile and preferences from the recommendation service.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx

_REC_URL = os.getenv("RECOMMENDATION_SERVICE_URL", "http://localhost:5001")


async def user_profile(params: Dict[str, Any]) -> Optional[dict]:
    user_id = params.get("user_id") or params.get("userId")
    if not user_id:
        return None

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            pref_r = await client.get(
                f"{_REC_URL}/api/recommendations/{user_id}/preferences"
            )
            pref_r.raise_for_status()
            prefs = pref_r.json().get("preferences", [])
        except Exception:
            prefs = []

        try:
            wl_r = await client.get(
                f"{_REC_URL}/api/recommendations/{user_id}/watchlist",
                params={"limit": 50},
            )
            wl_r.raise_for_status()
            watchlist = wl_r.json().get("watchlist", [])
        except Exception:
            watchlist = []

    return {
        "user_id": user_id,
        "preferences": prefs,
        "watchlist": watchlist,
        "watched_ids": [
            w["movie_id"]
            for w in watchlist
            if w.get("status") in ("watched", "rated", "liked", "disliked")
        ],
    }
