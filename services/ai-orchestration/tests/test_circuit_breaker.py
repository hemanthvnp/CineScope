"""Unit tests for the circuit breaker state machine — no network needed.
Run with:  pytest services/ai-orchestration/tests -v
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orchestrator.circuit_breaker import CircuitBreaker, CircuitOpenError


async def _call(cb: CircuitBreaker, fail: bool) -> None:
    try:
        async with cb:
            if fail:
                raise RuntimeError("boom")
    except RuntimeError:
        pass


def _run(cb: CircuitBreaker, outcomes: str) -> None:
    """outcomes: 'f' = failing call, 's' = successful call"""
    async def scenario():
        for o in outcomes:
            await _call(cb, fail=o == "f")
    asyncio.run(scenario())


def test_consecutive_failures_open_the_circuit():
    cb = CircuitBreaker("t", failure_threshold=5)
    _run(cb, "fffff")
    assert cb.state == "open"
    with pytest.raises(CircuitOpenError):
        _run(cb, "s")


def test_sporadic_failures_between_successes_never_open_it():
    cb = CircuitBreaker("t", failure_threshold=5)
    _run(cb, "ffffs" * 10)
    assert cb.state == "closed"


def test_half_open_probe_closes_on_success_and_reopens_on_failure():
    cb = CircuitBreaker("t", failure_threshold=2, recovery_timeout=0)
    _run(cb, "ff")
    _run(cb, "s")                                   # recovery_timeout elapsed → probe succeeds
    assert cb.state == "closed"
    _run(cb, "fff")
    assert cb.state == "open"
    _run(cb, "f")                                   # failed probe → straight back to open
    assert cb.state == "open"
