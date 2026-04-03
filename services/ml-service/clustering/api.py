"""
Movie Clustering Microservice - REST API

FastAPI-based REST API for movie clustering service.

Endpoints:
  GET  /health           - Service health check
  POST /fetch-movies     - Fetch and cache TMDB movie data
  GET  /cluster          - Run clustering and return all clusters
  GET  /clusters         - Get cached clustering results
  GET  /recommend/{id}   - Get recommendations from same cluster
  POST /recluster        - Force re-clustering with new parameters

Run with:
  uvicorn clustering.api:app --host 0.0.0.0 --port 8001 --reload
"""

import os
import traceback
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Dict, List, Optional
from enum import Enum

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .tmdb_service import TMDBService, Movie
from .preprocessing import MoviePreprocessor, PreprocessedData, summarize_preprocessed_data, ERA_BUCKETS, ERA_ORDER
from .clustering import MovieClusterer, ClusteringResult


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class Settings:
    """Application settings from environment variables."""
    TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
    PORT = int(os.getenv("CLUSTERING_PORT", 8001))
    DEFAULT_MOVIE_COUNT = 1000
    MIN_MOVIE_COUNT = 100
    MAX_MOVIE_COUNT = 3000
    DEFAULT_K = None  # Auto-detect
    K_RANGE = (3, 15)


settings = Settings()


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class ClusteringAlgorithm(str, Enum):
    KMEANS = "kmeans"
    DBSCAN = "dbscan"


class FetchMoviesRequest(BaseModel):
    total_movies: int = Field(
        default=settings.DEFAULT_MOVIE_COUNT,
        ge=settings.MIN_MOVIE_COUNT,
        le=settings.MAX_MOVIE_COUNT,
        description="Number of movies to fetch"
    )
    diverse: bool = Field(
        default=True,
        description="Fetch diverse languages (recommended)"
    )
    clear_cache: bool = Field(
        default=False,
        description="Clear existing cache before fetching"
    )


class ClusterRequest(BaseModel):
    algorithm: ClusteringAlgorithm = Field(
        default=ClusteringAlgorithm.KMEANS,
        description="Clustering algorithm"
    )
    n_clusters: Optional[int] = Field(
        default=None,
        ge=2,
        le=50,
        description="Number of clusters (None for auto)"
    )
    auto_k: bool = Field(
        default=True,
        description="Auto-detect optimal K (KMeans only)"
    )
    eps: float = Field(
        default=0.5,
        ge=0.1,
        le=2.0,
        description="DBSCAN eps parameter"
    )
    min_samples: int = Field(
        default=5,
        ge=2,
        le=50,
        description="DBSCAN min_samples parameter"
    )


class MovieResponse(BaseModel):
    id: int
    title: str
    overview: str
    release_date: str
    language: str
    genres: List[str]
    poster_path: str
    vote_average: float
    popularity: float


class ClusterResponse(BaseModel):
    cluster_id: int
    size: int
    dominant_language: str
    top_genres: List[str]
    era: str
    movies: List[MovieResponse] = []


class ClusteringResponse(BaseModel):
    algorithm: str
    n_clusters: int
    total_movies: int
    metrics: Dict
    clusters: List[ClusterResponse]


class HealthResponse(BaseModel):
    service: str = "movie-clustering-service"
    status: str = "healthy"
    version: str = "1.0.0"
    data_loaded: bool = False
    movies_count: int = 0
    clusters_count: int = 0


class FilterOptionsResponse(BaseModel):
    genres: List[str]
    languages: List[Dict[str, str]]  # [{code: "en", name: "English"}, ...]
    eras: List[Dict[str, str]]  # [{id: "Modern", label: "Modern (2000-2015)"}, ...]


class FilteredMoviesResponse(BaseModel):
    filters_applied: Dict[str, Optional[str]]
    total_matches: int
    movies: List[MovieResponse]


# ---------------------------------------------------------------------------
# Global State (in-memory for simplicity; use Redis/DB in production)
# ---------------------------------------------------------------------------

class ServiceState:
    def __init__(self):
        self.tmdb_service: Optional[TMDBService] = None
        self.preprocessor: Optional[MoviePreprocessor] = None
        self.clusterer: Optional[MovieClusterer] = None
        self.movies: List[Movie] = []
        self.preprocessed_data: Optional[PreprocessedData] = None
        self.clustering_result: Optional[ClusteringResult] = None
        self.genre_map: Dict[int, str] = {}

    def reset(self):
        self.movies = []
        self.preprocessed_data = None
        self.clustering_result = None


state = ServiceState()


# ---------------------------------------------------------------------------
# Application Lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    try:
        if settings.TMDB_API_KEY:
            state.tmdb_service = TMDBService(api_key=settings.TMDB_API_KEY)
            state.genre_map = state.tmdb_service.fetch_genre_list()
            print(f"[clustering-api] TMDB service initialized with {len(state.genre_map)} genres")
        else:
            print("[clustering-api] WARNING: TMDB_API_KEY not set")

        state.preprocessor = MoviePreprocessor(genre_map=state.genre_map)
        state.clusterer = MovieClusterer(k_range=settings.K_RANGE)

        print("[clustering-api] Service ready")
    except Exception as e:
        print(f"[clustering-api] Initialization error: {e}")
        traceback.print_exc()

    yield

    print("[clustering-api] Shutting down")


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Movie Clustering Microservice",
    description="Clusters movies by language, genre, and era using ML algorithms",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def movie_to_response(movie: Movie) -> MovieResponse:
    """Convert Movie dataclass to API response model."""
    genres = [state.genre_map.get(gid, str(gid)) for gid in movie.genre_ids]
    return MovieResponse(
        id=movie.id,
        title=movie.title,
        overview=movie.overview,
        release_date=movie.release_date,
        language=movie.original_language,
        genres=genres,
        poster_path=movie.poster_path or "",
        vote_average=movie.vote_average,
        popularity=movie.popularity
    )


def cluster_to_response(cluster_id: int, include_movies: bool = False) -> ClusterResponse:
    """Convert cluster info to API response."""
    if not state.clustering_result:
        raise HTTPException(status_code=400, detail="No clustering result available")

    cluster_info = state.clustering_result.get_cluster(cluster_id)
    if not cluster_info:
        raise HTTPException(status_code=404, detail=f"Cluster {cluster_id} not found")

    movies = []
    if include_movies:
        cluster_movies = state.clustering_result.get_movies_in_cluster(cluster_id)
        movies = [movie_to_response(m) for m in cluster_movies[:100]]  # Limit for response size

    return ClusterResponse(
        cluster_id=cluster_info.cluster_id,
        size=cluster_info.size,
        dominant_language=cluster_info.dominant_language,
        top_genres=cluster_info.top_genres,
        era=cluster_info.era,
        movies=movies
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Service health check endpoint."""
    return HealthResponse(
        data_loaded=len(state.movies) > 0,
        movies_count=len(state.movies),
        clusters_count=state.clustering_result.n_clusters if state.clustering_result else 0
    )


@app.post("/fetch-movies")
async def fetch_movies(request: FetchMoviesRequest = None):
    """
    Fetch movies from TMDB and cache them.

    This endpoint fetches movie data from TMDB API with pagination,
    stores it in memory, and optionally saves to disk cache.
    """
    if request is None:
        request = FetchMoviesRequest()

    if not state.tmdb_service:
        raise HTTPException(status_code=500, detail="TMDB service not initialized")

    try:
        # Clear cache if requested
        if request.clear_cache:
            state.tmdb_service.clear_cache()
            state.reset()

        # Fetch movies
        if request.diverse:
            movies = state.tmdb_service.fetch_diverse_movies(
                total_movies=request.total_movies
            )
        else:
            movies = state.tmdb_service.fetch_movies(
                total_movies=request.total_movies
            )

        state.movies = movies
        state.genre_map = state.tmdb_service.genre_map

        # Update preprocessor with latest genre map
        state.preprocessor = MoviePreprocessor(genre_map=state.genre_map)

        return {
            "status": "success",
            "movies_fetched": len(movies),
            "cache_stats": state.tmdb_service.get_cache_stats()
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cluster")
async def run_clustering(
    algorithm: ClusteringAlgorithm = Query(default=ClusteringAlgorithm.KMEANS),
    n_clusters: Optional[int] = Query(default=None, ge=2, le=50),
    auto_k: bool = Query(default=True),
    include_movies: bool = Query(default=False),
    eps: float = Query(default=0.5),
    min_samples: int = Query(default=5)
):
    """
    Run clustering on fetched movies and return all clusters.

    Parameters:
    - algorithm: kmeans or dbscan
    - n_clusters: Number of clusters (None for auto with kmeans)
    - auto_k: Auto-detect optimal K (kmeans only)
    - include_movies: Include movie list in response
    """
    if not state.movies:
        raise HTTPException(
            status_code=400,
            detail="No movies loaded. Call POST /fetch-movies first."
        )

    try:
        # Preprocess data
        state.preprocessed_data = state.preprocessor.fit_transform(state.movies)
        summary = summarize_preprocessed_data(state.preprocessed_data)

        # Run clustering
        if algorithm == ClusteringAlgorithm.KMEANS:
            result = state.clusterer.cluster_kmeans(
                data=state.preprocessed_data,
                n_clusters=n_clusters,
                auto_k=auto_k
            )
        else:
            result = state.clusterer.cluster_dbscan(
                data=state.preprocessed_data,
                eps=eps,
                min_samples=min_samples
            )

        state.clustering_result = result

        # Build response
        clusters = [
            cluster_to_response(c.cluster_id, include_movies)
            for c in result.clusters
        ]

        return ClusteringResponse(
            algorithm=result.algorithm,
            n_clusters=result.n_clusters,
            total_movies=len(state.movies),
            metrics=result.metrics,
            clusters=clusters
        )

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recluster")
async def recluster(request: ClusterRequest):
    """
    Force re-clustering with new parameters.

    Useful for experimenting with different configurations.
    """
    if not state.preprocessed_data:
        raise HTTPException(
            status_code=400,
            detail="No preprocessed data. Call POST /fetch-movies and GET /cluster first."
        )

    try:
        if request.algorithm == ClusteringAlgorithm.KMEANS:
            result = state.clusterer.cluster_kmeans(
                data=state.preprocessed_data,
                n_clusters=request.n_clusters,
                auto_k=request.auto_k
            )
        else:
            result = state.clusterer.cluster_dbscan(
                data=state.preprocessed_data,
                eps=request.eps,
                min_samples=request.min_samples
            )

        state.clustering_result = result

        return {
            "status": "success",
            "algorithm": result.algorithm,
            "n_clusters": result.n_clusters,
            "metrics": result.metrics
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/clusters")
async def get_clusters(include_movies: bool = Query(default=False)):
    """
    Get cached clustering results.

    Returns all clusters from the most recent clustering run.
    """
    if not state.clustering_result:
        raise HTTPException(
            status_code=400,
            detail="No clustering results available. Run GET /cluster first."
        )

    clusters = [
        cluster_to_response(c.cluster_id, include_movies)
        for c in state.clustering_result.clusters
    ]

    return {
        "algorithm": state.clustering_result.algorithm,
        "n_clusters": state.clustering_result.n_clusters,
        "clusters": clusters
    }


@app.get("/clusters/{cluster_id}")
async def get_cluster(
    cluster_id: int,
    include_movies: bool = Query(default=True)
):
    """Get details for a specific cluster."""
    if not state.clustering_result:
        raise HTTPException(
            status_code=400,
            detail="No clustering results available"
        )

    return cluster_to_response(cluster_id, include_movies)


@app.get("/recommend/{movie_id}")
async def get_recommendations(
    movie_id: int,
    limit: int = Query(default=10, ge=1, le=50)
):
    """
    Get movie recommendations from the same cluster.

    Returns movies that are clustered with the given movie,
    sorted by popularity.
    """
    if not state.clustering_result:
        raise HTTPException(
            status_code=400,
            detail="No clustering results. Run clustering first."
        )

    # Find the movie's cluster
    cluster_id = state.clusterer.get_cluster_for_movie(movie_id)
    if cluster_id is None:
        raise HTTPException(
            status_code=404,
            detail=f"Movie {movie_id} not found in any cluster"
        )

    # Get similar movies
    similar = state.clusterer.get_similar_movies(movie_id, limit=limit)

    cluster_info = state.clustering_result.get_cluster(cluster_id)

    return {
        "movie_id": movie_id,
        "cluster_id": cluster_id,
        "cluster_info": {
            "dominant_language": cluster_info.dominant_language,
            "top_genres": cluster_info.top_genres,
            "era": cluster_info.era,
            "cluster_size": cluster_info.size
        },
        "recommendations": [movie_to_response(m) for m in similar]
    }


@app.get("/stats")
async def get_stats():
    """Get service statistics and data summary."""
    stats = {
        "movies_loaded": len(state.movies),
        "clustering_available": state.clustering_result is not None
    }

    if state.preprocessed_data:
        stats["preprocessing"] = summarize_preprocessed_data(state.preprocessed_data)

    if state.clustering_result:
        stats["clustering"] = {
            "algorithm": state.clustering_result.algorithm,
            "n_clusters": state.clustering_result.n_clusters,
            "metrics": state.clustering_result.metrics
        }

    if state.tmdb_service:
        stats["cache"] = state.tmdb_service.get_cache_stats()

    return stats


@app.delete("/cache")
async def clear_cache():
    """Clear all cached data and reset state."""
    if state.tmdb_service:
        files_cleared = state.tmdb_service.clear_cache()
    else:
        files_cleared = 0

    state.reset()

    return {
        "status": "success",
        "files_cleared": files_cleared,
        "state_reset": True
    }


# ---------------------------------------------------------------------------
# Filter Endpoints - Intersection of Genre, Language, Era
# ---------------------------------------------------------------------------

# Language code to name mapping
LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "hi": "Hindi",
    "pt": "Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
    "th": "Thai",
    "tr": "Turkish",
    "pl": "Polish",
    "nl": "Dutch",
    "sv": "Swedish",
    "da": "Danish",
    "no": "Norwegian",
    "fi": "Finnish",
    "id": "Indonesian",
    "ms": "Malay",
    "vi": "Vietnamese",
    "tl": "Tagalog",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "bn": "Bengali",
    "uk": "Ukrainian",
    "cs": "Czech",
    "el": "Greek",
    "he": "Hebrew",
    "hu": "Hungarian",
    "ro": "Romanian",
    "cn": "Cantonese",
}


def get_era_from_year(year: int) -> str:
    """Determine era bucket from release year."""
    for era, (start, end) in ERA_BUCKETS.items():
        if start <= year <= end:
            return era
    return "Recent"


def extract_year(release_date: str) -> Optional[int]:
    """Extract year from TMDB release_date string."""
    if not release_date or len(release_date) < 4:
        return None
    try:
        return int(release_date[:4])
    except ValueError:
        return None


@app.get("/filters/options", response_model=FilterOptionsResponse)
async def get_filter_options():
    """
    Get available filter options for genres, languages, and eras.

    Use this endpoint to populate filter dropdowns in the UI.
    Returns all unique values from the loaded movie dataset.
    """
    if not state.movies:
        raise HTTPException(
            status_code=400,
            detail="No movies loaded. Call POST /fetch-movies first."
        )

    # Collect unique genres
    genre_ids = set()
    for movie in state.movies:
        genre_ids.update(movie.genre_ids)

    genres = sorted([
        state.genre_map.get(gid, str(gid))
        for gid in genre_ids
    ])

    # Collect unique languages
    language_codes = set(m.original_language for m in state.movies if m.original_language)
    languages = sorted([
        {"code": code, "name": LANGUAGE_NAMES.get(code, code.upper())}
        for code in language_codes
    ], key=lambda x: x["name"])

    # Era options with labels
    eras = [
        {"id": "Classic", "label": "Classic (before 1980)"},
        {"id": "Old", "label": "Old (1980-1999)"},
        {"id": "Modern", "label": "Modern (2000-2015)"},
        {"id": "Recent", "label": "Recent (2016+)"},
    ]

    return FilterOptionsResponse(
        genres=genres,
        languages=languages,
        eras=eras
    )


@app.get("/filter", response_model=FilteredMoviesResponse)
async def filter_movies(
    genre: Optional[str] = Query(default=None, description="Genre name (e.g., 'Action')"),
    language: Optional[str] = Query(default=None, description="Language code (e.g., 'en')"),
    era: Optional[str] = Query(default=None, description="Era bucket (Classic, Old, Modern, Recent)"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum results"),
    sort_by: str = Query(default="popularity", description="Sort by: popularity, vote_average, release_date")
):
    """
    Filter movies by intersection of genre, language, and era.

    Returns movies that match ALL specified criteria (AND logic).
    Omit a parameter to not filter by that criterion.

    Examples:
    - /filter?genre=Action&language=en&era=Modern
      → English Action movies from 2000-2015
    - /filter?genre=Drama&era=Recent
      → Drama movies from 2016+ in any language
    - /filter?language=ko
      → All Korean movies
    """
    if not state.movies:
        raise HTTPException(
            status_code=400,
            detail="No movies loaded. Call POST /fetch-movies first."
        )

    # Validate era if provided
    if era and era not in ERA_BUCKETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid era. Must be one of: {', '.join(ERA_ORDER)}"
        )

    # Find genre_id from genre name
    genre_id = None
    if genre:
        for gid, gname in state.genre_map.items():
            if gname.lower() == genre.lower():
                genre_id = gid
                break
        if genre_id is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown genre: {genre}. Call GET /filters/options for valid genres."
            )

    # Filter movies by intersection
    filtered = []
    for movie in state.movies:
        # Check genre filter
        if genre_id is not None and genre_id not in movie.genre_ids:
            continue

        # Check language filter
        if language and movie.original_language != language:
            continue

        # Check era filter
        if era:
            year = extract_year(movie.release_date)
            if year is None:
                continue
            movie_era = get_era_from_year(year)
            if movie_era != era:
                continue

        filtered.append(movie)

    # Sort results
    if sort_by == "popularity":
        filtered.sort(key=lambda m: -m.popularity)
    elif sort_by == "vote_average":
        filtered.sort(key=lambda m: -m.vote_average)
    elif sort_by == "release_date":
        filtered.sort(key=lambda m: m.release_date or "", reverse=True)

    # Apply limit
    filtered = filtered[:limit]

    return FilteredMoviesResponse(
        filters_applied={
            "genre": genre,
            "language": language,
            "era": era
        },
        total_matches=len(filtered),
        movies=[movie_to_response(m) for m in filtered]
    )


@app.get("/filter/count")
async def filter_count(
    genre: Optional[str] = Query(default=None),
    language: Optional[str] = Query(default=None),
    era: Optional[str] = Query(default=None)
):
    """
    Get count of movies matching the filter criteria.

    Useful for showing "X movies found" in UI before loading full results.
    """
    if not state.movies:
        return {"count": 0, "filters_applied": {"genre": genre, "language": language, "era": era}}

    # Find genre_id from genre name
    genre_id = None
    if genre:
        for gid, gname in state.genre_map.items():
            if gname.lower() == genre.lower():
                genre_id = gid
                break

    count = 0
    for movie in state.movies:
        if genre_id is not None and genre_id not in movie.genre_ids:
            continue
        if language and movie.original_language != language:
            continue
        if era:
            year = extract_year(movie.release_date)
            if year is None:
                continue
            if get_era_from_year(year) != era:
                continue
        count += 1

    return {
        "count": count,
        "filters_applied": {"genre": genre, "language": language, "era": era}
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "clustering.api:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=True
    )
