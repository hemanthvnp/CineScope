"""
Movie Clustering Microservice - Configuration

Centralized configuration management using environment variables.
All settings can be overridden via environment variables.
"""

import os
from dataclasses import dataclass, field
from typing import Tuple, List
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class TMDBConfig:
    """TMDB API configuration."""
    api_key: str = field(default_factory=lambda: os.getenv("TMDB_API_KEY", ""))
    base_url: str = "https://api.themoviedb.org/3"
    timeout: int = 30
    max_retries: int = 3
    rate_limit_delay: float = 0.25  # seconds between requests


@dataclass
class CacheConfig:
    """Caching configuration."""
    enabled: bool = field(default_factory=lambda: os.getenv("CACHE_ENABLED", "true").lower() == "true")
    ttl_seconds: int = field(default_factory=lambda: int(os.getenv("CACHE_TTL", "3600")))
    directory: Path = field(default_factory=lambda: Path(__file__).parent / "cache")


@dataclass
class ClusteringConfig:
    """Clustering algorithm configuration."""
    # KMeans settings
    k_range: Tuple[int, int] = (3, 15)
    n_init: int = 10
    max_iter: int = 300
    random_state: int = 42

    # DBSCAN defaults
    dbscan_eps: float = 0.5
    dbscan_min_samples: int = 5

    # Feature engineering
    scale_features: bool = True
    min_language_count: int = 5  # Languages with fewer movies grouped as "other"
    fill_missing_year: int = 2000  # Default year for missing release dates


@dataclass
class APIConfig:
    """API server configuration."""
    host: str = field(default_factory=lambda: os.getenv("CLUSTERING_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("CLUSTERING_PORT", "8001")))
    reload: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")

    # Movie fetching limits
    default_movie_count: int = 1000
    min_movie_count: int = 100
    max_movie_count: int = 3000


@dataclass
class Config:
    """Main configuration container."""
    tmdb: TMDBConfig = field(default_factory=TMDBConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    clustering: ClusteringConfig = field(default_factory=ClusteringConfig)
    api: APIConfig = field(default_factory=APIConfig)

    def validate(self) -> List[str]:
        """Validate configuration and return list of warnings."""
        warnings = []

        if not self.tmdb.api_key:
            warnings.append("TMDB_API_KEY is not set - API calls will fail")

        if self.api.port < 1024 and os.name != "nt":
            warnings.append(f"Port {self.api.port} requires root privileges on Unix")

        return warnings


# Global configuration instance
config = Config()


# Convenience accessors
def get_tmdb_config() -> TMDBConfig:
    return config.tmdb


def get_cache_config() -> CacheConfig:
    return config.cache


def get_clustering_config() -> ClusteringConfig:
    return config.clustering


def get_api_config() -> APIConfig:
    return config.api


# Environment variable documentation
ENV_VARS = {
    "TMDB_API_KEY": "TMDB API key (required)",
    "CACHE_ENABLED": "Enable disk caching (default: true)",
    "CACHE_TTL": "Cache TTL in seconds (default: 3600)",
    "CLUSTERING_HOST": "API host (default: 0.0.0.0)",
    "CLUSTERING_PORT": "API port (default: 8001)",
    "DEBUG": "Enable debug mode with auto-reload (default: false)"
}


def print_config():
    """Print current configuration for debugging."""
    print("\n=== Movie Clustering Service Configuration ===\n")

    print("TMDB Configuration:")
    print(f"  API Key: {'***' + config.tmdb.api_key[-4:] if config.tmdb.api_key else 'NOT SET'}")
    print(f"  Base URL: {config.tmdb.base_url}")

    print("\nCache Configuration:")
    print(f"  Enabled: {config.cache.enabled}")
    print(f"  TTL: {config.cache.ttl_seconds}s")
    print(f"  Directory: {config.cache.directory}")

    print("\nClustering Configuration:")
    print(f"  K Range: {config.clustering.k_range}")
    print(f"  Scale Features: {config.clustering.scale_features}")

    print("\nAPI Configuration:")
    print(f"  Host: {config.api.host}")
    print(f"  Port: {config.api.port}")
    print(f"  Debug/Reload: {config.api.reload}")

    warnings = config.validate()
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  - {w}")

    print()


if __name__ == "__main__":
    print_config()
