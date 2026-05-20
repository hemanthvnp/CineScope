"""
Watch-providers tool — wraps TMDB /movie/{id}/watch/providers.
Fetches providers for a list of movie IDs concurrently.
Called by the aggregator, not the execution engine directly.
"""
from __future__ import annotations

import asyncio
import os
from typing import Dict, List

import httpx

_TMDB_KEY = os.getenv("TMDB_API_KEY", "")
_TMDB_BASE = "https://api.themoviedb.org/3"
_LOGO_BASE = "https://image.tmdb.org/t/p/original"


async def _fetch_providers_for_movie(
    client: httpx.AsyncClient,
    movie_id: int,
    country: str,
) -> List[dict]:
    try:
        r = await client.get(
            f"{_TMDB_BASE}/movie/{movie_id}/watch/providers",
            params={"api_key": _TMDB_KEY},
        )
        r.raise_for_status()
        country_data = r.json().get("results", {}).get(country.upper(), {})
        providers = []
        for ptype in ("flatrate", "rent", "buy"):
            for p in country_data.get(ptype, []):
                providers.append({
                    "name": p.get("provider_name", ""),
                    "type": ptype,
                    "logo": f"{_LOGO_BASE}{p['logo_path']}" if p.get("logo_path") else None,
                })
        # Deduplicate by name, prefer flatrate
        seen: dict[str, dict] = {}
        for p in providers:
            name = p["name"]
            if name not in seen or p["type"] == "flatrate":
                seen[name] = p
        return list(seen.values())[:4]
    except Exception:
        return []


async def fetch_providers(
    movie_ids: List[int],
    country: str = "US",
) -> Dict[int, List[dict]]:
    """Return {movie_id: [provider, …]} for all supplied IDs."""
    if not movie_ids:
        return {}

    async with httpx.AsyncClient(
        timeout=6.0,
        limits=httpx.Limits(max_connections=30),
    ) as client:
        tasks = [
            _fetch_providers_for_movie(client, mid, country)
            for mid in movie_ids
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    return {
        mid: ([] if isinstance(res, Exception) else res)
        for mid, res in zip(movie_ids, results)
    }
