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

# Configuration
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
BASE_URL = "https://api.themoviedb.org/3"
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_TTL = 3600  # 1 hour for disk cache


@dataclass
class Movie:
    """Movie data structure matching TMDB response fields."""
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
    """
    Service for fetching and caching TMDB movie data.

    Features:
    - Pagination support for bulk fetching
    - Disk-based caching to avoid repeated API calls
    - Automatic rate limiting with retry logic
    - Genre mapping from IDs to names
    """

    def __init__(self, api_key: str = None, cache_enabled: bool = True):
        """
        Initialize TMDB service.

        Args:
            api_key: TMDB API key (defaults to env variable)
            cache_enabled: Whether to use disk caching
        """
        self.api_key = api_key or TMDB_API_KEY
        if not self.api_key:
            raise ValueError("TMDB_API_KEY is required")

        self.cache_enabled = cache_enabled
        self.session = requests.Session()
        self.genre_map: Dict[int, str] = {}

        # Ensure cache directory exists
        if self.cache_enabled:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, cache_key: str) -> Path:
        """Generate cache file path from key."""
        key_hash = hashlib.md5(cache_key.encode()).hexdigest()
        return CACHE_DIR / f"{key_hash}.json"

    def _load_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Load data from disk cache if valid."""
        if not self.cache_enabled:
            return None

        cache_path = self._get_cache_path(cache_key)
        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)

            # Check TTL
            if time.time() - cached.get("timestamp", 0) > CACHE_TTL:
                cache_path.unlink(missing_ok=True)
                return None

            return cached.get("data")
        except (json.JSONDecodeError, IOError):
            return None

    def _save_to_cache(self, cache_key: str, data: Dict) -> None:
        """Save data to disk cache."""
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
        """
        Make GET request to TMDB API with retry logic.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response as dict
        """
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
        """
        Fetch genre ID to name mapping from TMDB.

        Returns:
            Dict mapping genre_id -> genre_name
        """
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
        """
        Fetch bulk movies from TMDB using pagination.

        Args:
            total_movies: Target number of movies (500-2000 recommended)
            sort_by: TMDB sort criteria
            languages: Filter by original_language codes (None = all)

        Returns:
            List of Movie objects
        """
        cache_key = f"movies_{total_movies}_{sort_by}_{languages}"
        cached = self._load_from_cache(cache_key)
        if cached:
            print(f"[tmdb_service] Loaded {len(cached)} movies from cache")
            return [Movie(**m) for m in cached]

        # Ensure genre map is loaded
        if not self.genre_map:
            self.fetch_genre_list()

        movies: List[Movie] = []
        seen_ids = set()
        pages_per_batch = 20  # TMDB returns 20 results per page
        pages_needed = (total_movies // pages_per_batch) + 1

        print(f"[tmdb_service] Fetching ~{total_movies} movies ({pages_needed} pages)...")

        for page in range(1, min(pages_needed + 1, 500)):  # TMDB max 500 pages
            if len(movies) >= total_movies:
                break

            params = {
                "sort_by": sort_by,
                "page": page,
                "vote_count.gte": 10  # Filter low-quality entries
            }

            # Optionally filter by language
            if languages and len(languages) == 1:
                params["with_original_language"] = languages[0]

            try:
                data = self._api_request("/discover/movie", params)
                results = data.get("results", [])

                for m in results:
                    movie_id = m["id"]
                    if movie_id in seen_ids:
                        continue

                    # Filter by language if multiple specified
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

                # Progress logging
                if page % 10 == 0:
                    print(f"[tmdb_service] Fetched {len(movies)} movies (page {page})...")

                # Rate limiting: ~4 requests per second
                time.sleep(0.25)

            except Exception as e:
                print(f"[tmdb_service] Error on page {page}: {e}")
                continue

        print(f"[tmdb_service] Fetched {len(movies)} movies total")

        # Cache results
        self._save_to_cache(cache_key, [m.to_dict() for m in movies])
        return movies

    def fetch_diverse_movies(self, total_movies: int = 1500) -> List[Movie]:
        """
        Fetch movies with diverse languages for better clustering.

        Fetches from multiple language pools to ensure variety:
        - English (en)
        - Spanish (es)
        - French (fr)
        - Korean (ko)
        - Japanese (ja)
        - Hindi (hi)
        - And more through general discovery

        Args:
            total_movies: Total target movies

        Returns:
            List of Movie objects with diverse languages
        """
        cache_key = f"diverse_movies_{total_movies}"
        cached = self._load_from_cache(cache_key)
        if cached:
            print(f"[tmdb_service] Loaded {len(cached)} diverse movies from cache")
            return [Movie(**m) for m in cached]

        # Language distribution for diversity
        language_targets = [
            ("en", 0.35),   # English: 35%
            ("es", 0.10),   # Spanish: 10%
            ("fr", 0.08),   # French: 8%
            ("ko", 0.10),   # Korean: 10%
            ("ja", 0.10),   # Japanese: 10%
            ("hi", 0.08),   # Hindi: 8%
            ("zh", 0.05),   # Chinese: 5%
            ("de", 0.04),   # German: 4%
            ("it", 0.04),   # Italian: 4%
            (None, 0.06),   # General discovery: 6%
        ]

        all_movies: List[Movie] = []
        seen_ids = set()

        for lang, ratio in language_targets:
            target = int(total_movies * ratio)
            movies = self.fetch_movies(
                total_movies=target + 50,  # Fetch extra to account for duplicates
                languages=[lang] if lang else None
            )

            for m in movies:
                if m.id not in seen_ids and len(all_movies) < total_movies:
                    seen_ids.add(m.id)
                    all_movies.append(m)

        print(f"[tmdb_service] Fetched {len(all_movies)} diverse movies")

        # Cache results
        self._save_to_cache(cache_key, [m.to_dict() for m in all_movies])
        return all_movies

    def get_genre_name(self, genre_id: int) -> str:
        """Get genre name from ID."""
        if not self.genre_map:
            self.fetch_genre_list()
        return self.genre_map.get(genre_id, "Unknown")

    def get_genre_names(self, genre_ids: List[int]) -> List[str]:
        """Get multiple genre names from IDs."""
        return [self.get_genre_name(gid) for gid in genre_ids]

    def clear_cache(self) -> int:
        """Clear all cached data. Returns number of files deleted."""
        if not CACHE_DIR.exists():
            return 0

        count = 0
        for cache_file in CACHE_DIR.glob("*.json"):
            cache_file.unlink()
            count += 1

        print(f"[tmdb_service] Cleared {count} cache files")
        return count

    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        if not CACHE_DIR.exists():
            return {"files": 0, "size_kb": 0}

        files = list(CACHE_DIR.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files)

        return {
            "files": len(files),
            "size_kb": round(total_size / 1024, 2)
        }
