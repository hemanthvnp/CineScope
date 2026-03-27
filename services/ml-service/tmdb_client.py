"""
CineScope ML Service — TMDB API Client

Fetches movie data directly from TMDB instead of local MongoDB.
Includes in-memory caching with TTL.
"""

import os
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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


# Setup session with retry strategy
_session = requests.Session()
_retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)
_adapter = HTTPAdapter(max_retries=_retry_strategy)
_session.mount("http://", _adapter)
_session.mount("https://", _adapter)

def _tmdb_get(path, params=None):
    """Make a GET request to TMDB API."""
    if params is None:
        params = {}
    params["api_key"] = TMDB_API_KEY

    try:
        resp = _session.get(f"{BASE_URL}{path}", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[tmdb_client] ERROR for {path}: {e}")
        raise


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
                time.sleep(0.5) # Increased to 0.5s to respect TMDB rate limits better during massive fetch
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


def fetch_movie_details(movie_id):
    """Fetch details for a specific movie by TMDB ID."""
    cache_key = f"movie_details_{movie_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        m = _tmdb_get(f"/movie/{movie_id}")
        movie = {
            "movie_id": m["id"],
            "title": m.get("title", ""),
            "overview": m.get("overview", ""),
            "poster_path": m.get("poster_path", ""),
            "vote_average": m.get("vote_average", 0),
            "vote_count": m.get("vote_count", 0),
            "popularity": m.get("popularity", 0),
            "release_date": m.get("release_date", ""),
            "language": m.get("original_language", "en"),
            "genre_ids": [g["id"] for g in m.get("genres", [])]
        }
        _cache_set(cache_key, movie)
        return movie
    except Exception as e:
        print(f"[tmdb_client] Failed to fetch details for movie {movie_id}: {e}")
        return None
