"""
TMDB Service - Data Ingestion Module

Fetches movie data from TMDB API for clustering purposes.
Implements pagination, caching, and error handling.

Endpoints used:
  - /discover/movie (bulk movie fetching)
  - /genre/movie/list (genre ID to name mapping)
"""

import os
import time
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

import requests

TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
BASE_URL = "https://api.themoviedb.org/3"
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_TTL = 3600
API_RATE_LIMIT = 40


@dataclass
class Movie:
    id: int
    title: str
    overview: str
    release_date: str
    original_language: str
    genre_ids: List[int]
    vote_average: float = 0.0
    vote_count: int = 0
    popularity: float = 0.0
    poster_path: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


class TMDBService:

    def __init__(self, api_key: str = None, cache_enabled: bool = True):
        self.api_key = api_key or TMDB_API_KEY
        if not self.api_key:
            raise ValueError("TMDB_API_KEY is required")

        self.cache_enabled = cache_enabled
        self.session = requests.Session()
        self.genre_map: Dict[int, str] = {}

        if self.cache_enabled:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, cache_key: str) -> Path:
        key_hash = hashlib.md5(cache_key.encode()).hexdigest()
        return CACHE_DIR / f"{key_hash}.json"

    def _load_from_cache(self, cache_key: str) -> Optional[Dict]:
        if not self.cache_enabled:
            return None

        cache_path = self._get_cache_path(cache_key)
        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if time.time() - cached.get("timestamp", 0) > CACHE_TTL:
                cache_path.unlink(missing_ok=True)
                return None

            return cached.get("data")
        except (json.JSONDecodeError, IOError):
            return None

    def _save_to_cache(self, cache_key: str, data: Dict) -> None:
        if not self.cache_enabled:
            return

        cache_path = self._get_cache_path(cache_key)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": time.time(),
                    "data": data
                }, f)
        except IOError as e:
            print(f"[tmdb_service] Cache write failed: {e}")

    def _api_request(self, endpoint: str, params: Dict = None) -> Dict:
        if params is None:
            params = {}
        params["api_key"] = self.api_key

        for attempt in range(3):
            try:
                response = self.session.get(
                    f"{BASE_URL}{endpoint}",
                    params=params,
                    timeout=30
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt == 2:
                    raise RuntimeError(f"TMDB API request failed: {e}")
                sleep_time = (attempt + 1) * 2
                print(f"[tmdb_service] Retry {attempt + 1}/3 for {endpoint}: {e}")
                time.sleep(sleep_time)

    def fetch_genre_list(self) -> Dict[int, str]:
        cache_key = "genre_list"
        cached = self._load_from_cache(cache_key)
        if cached:
            self.genre_map = cached
            return cached

        data = self._api_request("/genre/movie/list")
        genres = {g["id"]: g["name"] for g in data.get("genres", [])}

        self._save_to_cache(cache_key, genres)
        self.genre_map = genres
        return genres

    def fetch_movies(
        self,
        total_movies: int = 1000,
        sort_by: str = "popularity.desc",
        languages: List[str] = None
    ) -> List[Movie]:
        cache_key = f"movies_{total_movies}_{sort_by}_{languages}"
        cached = self._load_from_cache(cache_key)
        if cached:
            print(f"[tmdb_service] Loaded {len(cached)} movies from cache")
            return [Movie(**m) for m in cached]
        if not self.genre_map:
            self.fetch_genre_list()

        movies: List[Movie] = []
        seen_ids = set()
        pages_per_batch = 20 
        pages_needed = (total_movies // pages_per_batch) + 1

        print(f"[tmdb_service] Fetching ~{total_movies} movies ({pages_needed} pages)...")

        for page in range(1, min(pages_needed + 1, 500)):
            if len(movies) >= total_movies:
                break

            params = {
                "sort_by": sort_by,
                "page": page,
                "vote_count.gte": 10  # Filter low-quality entries
            }
            if languages and len(languages) == 1:
                params["with_original_language"] = languages[0]

            try:
                data = self._api_request("/discover/movie", params)
                results = data.get("results", [])

                for m in results:
                    movie_id = m["id"]
                    if movie_id in seen_ids:
                        continue
                    if languages and m.get("original_language") not in languages:
                        continue

                    seen_ids.add(movie_id)
                    movies.append(Movie(
                        id=movie_id,
                        title=m.get("title", ""),
                        overview=m.get("overview", ""),
                        release_date=m.get("release_date", ""),
                        original_language=m.get("original_language", ""),
                        genre_ids=m.get("genre_ids", []),
                        vote_average=m.get("vote_average", 0),
                        vote_count=m.get("vote_count", 0),
                        popularity=m.get("popularity", 0),
                        poster_path=m.get("poster_path", "")
                    ))
                if page % 10 == 0:
                    print(f"[tmdb_service] Fetched {len(movies)} movies (page {page})...")
                time.sleep(0.25)

            except Exception as e:
                print(f"[tmdb_service] Error on page {page}: {e}")
                continue

        print(f"[tmdb_service] Fetched {len(movies)} movies total")
        self._save_to_cache(cache_key, [m.to_dict() for m in movies])
        return movies

    def fetch_diverse_movies(self, total_movies: int = 1500) -> List[Movie]:
        cache_key = f"diverse_movies_{total_movies}"
        cached = self._load_from_cache(cache_key)
        if cached:
            print(f"[tmdb_service] Loaded {len(cached)} diverse movies from cache")
            return [Movie(**m) for m in cached]

        language_targets = [
            ("es", 0.10),
            ("fr", 0.08),
            ("ko", 0.10),
            ("ja", 0.10),
            ("hi", 0.08),
            ("zh", 0.05),
            ("de", 0.04),
            (None, 0.06),
        ]

        all_movies: List[Movie] = []
        seen_ids = set()

        for lang, ratio in language_targets:
            target = int(total_movies * ratio)
            movies = self.fetch_movies(
                total_movies=target + 50,
                languages=[lang] if lang else None
            )

            for m in movies:
                if m.id not in seen_ids and len(all_movies) < total_movies:
                    seen_ids.add(m.id)
                    all_movies.append(m)

        print(f"[tmdb_service] Fetched {len(all_movies)} diverse movies")
        self._save_to_cache(cache_key, [m.to_dict() for m in all_movies])
        return all_movies

    def get_genre_name(self, genre_id: int) -> str:
        if not self.genre_map:
            self.fetch_genre_list()
        return self.genre_map.get(genre_id, "Unknown")

    def get_genre_names(self, genre_ids: List[int]) -> List[str]:
        return [self.get_genre_name(gid) for gid in genre_ids]

    def clear_cache(self) -> int:
        if not CACHE_DIR.exists():
            return 0

        count = 0
        for cache_file in CACHE_DIR.glob("*.json"):
            cache_file.unlink()
            count += 1

        print(f"[tmdb_service] Cleared {count} cache files")
        return count

    def get_cache_stats(self) -> Dict:
        if not CACHE_DIR.exists():
            return {"files": 0, "size_kb": 0}

        files = list(CACHE_DIR.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files)

        return {
            "files": len(files),
            "size_kb": round(total_size / 1024, 2)
        }
