"""
Async circuit breaker — three-state machine per service.

States:
  CLOSED   → normal operation, failures are counted
  OPEN     → requests blocked immediately; re-checked after recovery_timeout
  HALF_OPEN→ probe: one request allowed through; success → CLOSED, fail → OPEN
"""
from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Dict, Optional


class State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    def __init__(self, name: str):
        super().__init__(f"Circuit '{name}' is OPEN — service unavailable")
        self.service = name


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = State.CLOSED
        self._failure_count = 0
        self._opened_at: Optional[float] = None
        self._lock = asyncio.Lock()

    # ── Context manager ───────────────────────────────────────────────────────

    async def __aenter__(self) -> "CircuitBreaker":
        async with self._lock:
            if self._state == State.OPEN:
                elapsed = time.monotonic() - (self._opened_at or 0)
                if elapsed >= self.recovery_timeout:
                    self._state = State.HALF_OPEN
                    print(f"[cb:{self.name}] → HALF_OPEN (probing)")
                else:
                    raise CircuitOpenError(self.name)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        async with self._lock:
            if exc_type is not None:
                self._failure_count += 1
                if (
                    self._state in (State.CLOSED, State.HALF_OPEN)
                    and self._failure_count >= self.failure_threshold
                ):
                    self._state = State.OPEN
                    self._opened_at = time.monotonic()
                    print(
                        f"[cb:{self.name}] → OPEN "
                        f"({self._failure_count} failures)"
                    )
            else:
                if self._state == State.HALF_OPEN:
                    self._state = State.CLOSED
                    self._failure_count = 0
                    self._opened_at = None
                    print(f"[cb:{self.name}] → CLOSED (recovered)")
        return False  # never suppress exceptions

    # ── Introspection ─────────────────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state.value

    def is_open(self) -> bool:
        return self._state == State.OPEN


# ── Global registry ───────────────────────────────────────────────────────────

_registry: Dict[str, CircuitBreaker] = {}


def get_breaker(name: str) -> CircuitBreaker:
    if name not in _registry:
        _registry[name] = CircuitBreaker(name=name)
    return _registry[name]


def all_states() -> Dict[str, str]:
    return {name: cb.state for name, cb in _registry.items()}
