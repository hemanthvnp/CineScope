"""
CineScope ML Service — TMDB API Client

Fetches movie data directly from TMDB instead of local MongoDB.
Includes in-memory caching with TTL.
"""

import os
import time
import requests

TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
BASE_URL = "https://api.themoviedb.org/3"

# Simple TTL cache
_cache = {}
CACHE_TTL = 900  # 15 minutes


def _cache_get(key):
    entry = _cache.get(key)
    if entry is None:
        return None
    if time.time() - entry["ts"] > CACHE_TTL:
        del _cache[key]
        return None
    return entry["data"]


def _cache_set(key, data):
    _cache[key] = {"data": data, "ts": time.time()}


_session = requests.Session()

def _tmdb_get(path, params=None):
    """Make a GET request to TMDB API with retry and backoff."""
    if params is None:
        params = {}
    params["api_key"] = TMDB_API_KEY

    for attempt in range(3):
        try:
            resp = _session.get(f"{BASE_URL}{path}", params=params, timeout=20)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt == 2:
                print(f"[tmdb_client] FINAL FAILURE for {path}: {e}")
                raise
            sleep_time = (attempt + 1) * 2
            print(f"[tmdb_client] Retry {attempt+1} for {path} after {sleep_time}s due to: {e}")
            time.sleep(sleep_time)


def fetch_popular_movies(pages=5):
    """
    Fetch multiple pages of popular movies from TMDB.
    Returns list of movie dicts with keys matching the old DB schema.
    """
    cache_key = f"popular_{pages}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    all_movies = []
    for page in range(1, pages + 1):
        try:
            data = _tmdb_get("/movie/popular", {"page": page})
            for m in data.get("results", []):
                all_movies.append({
                    "movie_id": m["id"],
                    "title": m.get("title", ""),
                    "overview": m.get("overview", ""),
                    "poster_path": m.get("poster_path", ""),
                    "vote_average": m.get("vote_average", 0),
                    "vote_count": m.get("vote_count", 0),
                    "popularity": m.get("popularity", 0),
                    "release_date": m.get("release_date", ""),
                    "language": m.get("original_language", "en"),
                    "genre_ids": m.get("genre_ids", [])
                })
            if page < pages:
                time.sleep(0.25)
        except Exception as e:
            print(f"[tmdb_client] Failed to fetch popular page {page}: {e}")

    _cache_set(cache_key, all_movies)
    return all_movies


def fetch_trending_movies(limit=40):
    """Fetch trending movies from TMDB."""
    cache_key = f"trending_{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    results = []
    pages = (limit // 20) + 1
    for page in range(1, pages + 1):
        try:
            data = _tmdb_get("/trending/movie/week", {"page": page})
            for m in data.get("results", []):
                results.append({
                    "movie_id": m["id"],
                    "title": m.get("title", ""),
                    "overview": m.get("overview", ""),
                    "poster_path": m.get("poster_path", ""),
                    "vote_average": m.get("vote_average", 0),
                    "vote_count": m.get("vote_count", 0),
                    "popularity": m.get("popularity", 0),
                    "release_date": m.get("release_date", ""),
                    "language": m.get("original_language", "en"),
                    "genre_ids": m.get("genre_ids", [])
                })
        except Exception as e:
            print(f"[tmdb_client] Failed to fetch trending page {page}: {e}")

    sliced = results[:limit]
    _cache_set(cache_key, sliced)
    return sliced


def fetch_discover_movies(language="en", pages=2):
    """Fetch movies by specific original_language to ensure diverse candidates."""
    cache_key = f"discover_lang_{language}_{pages}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    results = []
    for page in range(1, pages + 1):
        try:
            data = _tmdb_get("/discover/movie", {
                "with_original_language": language,
                "sort_by": "popularity.desc",
                "page": page
            })
            for m in data.get("results", []):
                results.append({
                    "movie_id": m["id"],
                    "title": m.get("title", ""),
                    "overview": m.get("overview", ""),
                    "poster_path": m.get("poster_path", ""),
                    "vote_average": m.get("vote_average", 0),
                    "vote_count": m.get("vote_count", 0),
                    "popularity": m.get("popularity", 0),
                    "release_date": m.get("release_date", ""),
                    "language": m.get("original_language", "en"),
                    "genre_ids": m.get("genre_ids", [])
                })
        except Exception as e:
            print(f"[tmdb_client] Failed to fetch discover page {page}: {e}")

    _cache_set(cache_key, results)
    return results


def fetch_genre_list():
    """Fetch the TMDB genre list."""
    cached = _cache_get("genre_list")
    if cached is not None:
        return cached

    data = _tmdb_get("/genre/movie/list")
    genres = {g["id"]: g["name"] for g in data.get("genres", [])}
    _cache_set("genre_list", genres)
    return genres
