"""
CineScope Movie Clustering Microservice

A production-ready microservice that clusters movies based on:
- Language (original_language)
- Genre (genre_ids)
- Era (release_date year buckets)

Uses KMeans and DBSCAN clustering algorithms with automatic
optimal K selection via Silhouette Score analysis.
"""

from .tmdb_service import TMDBService
from .preprocessing import MoviePreprocessor
from .clustering import MovieClusterer

__all__ = ["TMDBService", "MoviePreprocessor", "MovieClusterer"]
__version__ = "1.0.0"
