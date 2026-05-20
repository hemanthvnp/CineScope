"""
Multi-tier cache:
  L1 — in-process LRU dict (sub-millisecond)
  L2 — Redis with TTL        (~1-2 ms, optional)

Falls back gracefully when Redis is unavailable.
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


def make_query_key(query: str, locale: str, user_segment: str = "anon") -> str:
    normalised = query.lower().strip()
    digest = hashlib.sha256(
        f"{normalised}|{locale}|{user_segment}".encode()
    ).hexdigest()[:20]
    return f"q:{digest}"


def make_tool_key(tool: str, params: dict) -> str:
    digest = hashlib.md5(
        json.dumps(params, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    return f"t:{tool}:{digest}"
