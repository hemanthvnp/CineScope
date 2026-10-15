"""
Multi-tier cache:
  L1 — in-process LRU dict (sub-millisecond)
  L2 — Redis with TTL        (~1-2 ms, optional)

Falls back gracefully when Redis is unavailable.

Responses are stored under two keys:
  q: — the normalised query text, checked before the LLM call (exact repeats skip everything)
  i: — the query's meaning (execution plan + filters), checked after the LLM call, so
       differently worded queries that resolve to the same plan share one entry
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Optional

# ── Redis (optional) ──────────────────────────────────────────────────────────
_redis: Any = None
_redis_available = False

try:
    import redis.asyncio as aioredis  # type: ignore

    _REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    _redis = aioredis.from_url(_REDIS_URL, decode_responses=True, socket_connect_timeout=1)
    _redis_available = True
except Exception:
    pass


# ── In-memory LRU (always available) ─────────────────────────────────────────
_MAX_ENTRIES = 1_000

_store: dict[str, tuple[Any, float, int]] = {}   # key → (data, stored_at, ttl)
_access: dict[str, float] = {}                    # key → last_access_time


def _mem_evict() -> None:
    if len(_store) < _MAX_ENTRIES:
        return
    oldest = sorted(_access, key=_access.__getitem__)[:(_MAX_ENTRIES // 5)]
    for k in oldest:
        _store.pop(k, None)
        _access.pop(k, None)


def _mem_get(key: str) -> Optional[Any]:
    entry = _store.get(key)
    if not entry:
        return None
    data, stored_at, ttl = entry
    if time.time() - stored_at > ttl:
        _store.pop(key, None)
        _access.pop(key, None)
        return None
    _access[key] = time.time()
    return data


def _mem_set(key: str, value: Any, ttl: int) -> None:
    _mem_evict()
    _store[key] = (value, time.time(), ttl)
    _access[key] = time.time()


# ── Public interface ──────────────────────────────────────────────────────────

async def cache_get(key: str) -> Optional[Any]:
    # L1
    hit = _mem_get(key)
    if hit is not None:
        return hit

    # L2 Redis
    if _redis_available and _redis:
        try:
            raw = await _redis.get(key)
            if raw:
                data = json.loads(raw)
                _mem_set(key, data, 60)          # promote to L1 with 60s TTL
                return data
        except Exception:
            pass

    return None


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    serialised = json.dumps(value, default=str)
    parsed = json.loads(serialised)             # normalise to plain Python types

    _mem_set(key, parsed, ttl)

    if _redis_available and _redis:
        try:
            await _redis.setex(key, ttl, serialised)
        except Exception:
            pass


def normalise_query(query: str) -> str:
    """'  90s Sci-Fi  movies? ' → '90s sci-fi movies'"""
    return " ".join(query.lower().split()).rstrip("?!.")


def canonical_params(params: dict) -> dict:
    """Drop empty values: tools treat a missing param and None / "" / [] the same way."""
    return {k: v for k, v in params.items() if v is not None and v != "" and v != []}


def make_query_key(query: str, locale: str, user_segment: str = "anon", filters: Optional[dict] = None) -> str:
    filter_part = json.dumps(filters, sort_keys=True, default=str) if filters else ""
    digest = hashlib.sha256(
        f"{normalise_query(query)}|{locale}|{user_segment}|{filter_part}".encode()
    ).hexdigest()[:20]
    return f"q:{digest}"


def make_intent_key(signature: dict) -> str:
    """Key a response by what the query means (plan + filters + options), not how it was worded."""
    digest = hashlib.sha256(
        json.dumps(signature, sort_keys=True, default=str).encode()
    ).hexdigest()[:20]
    return f"i:{digest}"


def make_tool_key(tool: str, params: dict) -> str:
    digest = hashlib.md5(
        json.dumps(canonical_params(params), sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    return f"t:{tool}:{digest}"
