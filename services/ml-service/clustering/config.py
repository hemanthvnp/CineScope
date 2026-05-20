import os
from dataclasses import dataclass, field
from typing import Tuple, List
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class TMDBConfig:
    api_key: str = field(default_factory=lambda: os.getenv("TMDB_API_KEY", ""))
    base_url: str = "https://api.themoviedb.org/3"
    timeout: int = 30
    max_retries: int = 3
    rate_limit_delay: float = 0.25


@dataclass
class CacheConfig:
    enabled: bool = field(default_factory=lambda: os.getenv("CACHE_ENABLED", "true").lower() == "true")
    ttl_seconds: int = field(default_factory=lambda: int(os.getenv("CACHE_TTL", "3600")))
    directory: Path = field(default_factory=lambda: Path(__file__).parent / "cache")


@dataclass
class ClusteringConfig:
    k_range: Tuple[int, int] = (3, 15)
    n_init: int = 10
    max_iter: int = 300
    random_state: int = 42

    dbscan_eps: float = 0.5
    dbscan_min_samples: int = 5

    scale_features: bool = True
    min_language_count: int = 5
    fill_missing_year: int = 2000


@dataclass
class APIConfig:
    host: str = field(default_factory=lambda: os.getenv("CLUSTERING_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("CLUSTERING_PORT", "8001")))
    reload: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")

    default_movie_count: int = 1000
    min_movie_count: int = 100
    max_movie_count: int = 3000


@dataclass
class Config:
    tmdb: TMDBConfig = field(default_factory=TMDBConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    clustering: ClusteringConfig = field(default_factory=ClusteringConfig)
    api: APIConfig = field(default_factory=APIConfig)

    def validate(self) -> List[str]:
        warnings = []

        if not self.tmdb.api_key:
            warnings.append("TMDB_API_KEY is not set - API calls will fail")

        if self.api.port < 1024 and os.name != "nt":
            warnings.append(f"Port {self.api.port} requires root privileges on Unix")

        return warnings


config = Config()


def get_tmdb_config() -> TMDBConfig:
    return config.tmdb


def get_cache_config() -> CacheConfig:
    return config.cache


def get_clustering_config() -> ClusteringConfig:
    return config.clustering


def get_api_config() -> APIConfig:
    return config.api


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
