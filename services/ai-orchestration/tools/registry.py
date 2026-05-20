"""
Central tool registry.
Each entry defines the async function, timeout, circuit-breaker name, and
default cache TTL so the execution engine never needs to know these details.
"""
from __future__ import annotations

from tools.tmdb_tool import (
    tmdb_search,
    tmdb_discover,
    tmdb_trending,
    tmdb_movie_details,
    tmdb_similar,
)
from tools.ml_recommend_tool import ml_recommend
from tools.semantic_search_tool import semantic_search
from tools.user_tool import user_profile
from tools.reviews_tool import movie_reviews

TOOL_REGISTRY: dict = {
    "tmdb_search": {
        "fn": tmdb_search,
        "timeout_ms": 5_000,
        "circuit_breaker": "tmdb",
        "cache_ttl": 900,
    },
    "tmdb_discover": {
        "fn": tmdb_discover,
        "timeout_ms": 5_000,
        "circuit_breaker": "tmdb",
        "cache_ttl": 600,
    },
    "tmdb_trending": {
        "fn": tmdb_trending,
        "timeout_ms": 5_000,
        "circuit_breaker": "tmdb",
        "cache_ttl": 600,
    },
    "tmdb_movie_details": {
        "fn": tmdb_movie_details,
        "timeout_ms": 5_000,
        "circuit_breaker": "tmdb",
        "cache_ttl": 3_600,
    },
    "tmdb_similar": {
        "fn": tmdb_similar,
        "timeout_ms": 5_000,
        "circuit_breaker": "tmdb",
        "cache_ttl": 1_800,
    },
    "ml_recommend": {
        "fn": ml_recommend,
        "timeout_ms": 15_000,
        "circuit_breaker": "ml_service",
        "cache_ttl": 600,
    },
    "semantic_search": {
        "fn": semantic_search,
        "timeout_ms": 3_000,
        "circuit_breaker": "vector",
        "cache_ttl": 300,
    },
    "user_profile": {
        "fn": user_profile,
        "timeout_ms": 4_000,
        "circuit_breaker": "user_service",
        "cache_ttl": 60,
    },
    "movie_reviews": {
        "fn": movie_reviews,
        "timeout_ms": 6_000,
        "circuit_breaker": "tmdb",
        "cache_ttl": 1_800,
    },
}
