"""Unit tests for LLM-failure handling — litellm is mocked, so no API key or network needed.
Run with:  pytest services/ai-orchestration/tests -v
"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

import litellm
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app as app_mod
import cache.semantic_cache as semantic_cache
from models.intent import QueryIntent
from models.query import QueryRequest
from orchestrator.aggregator import aggregate
from orchestrator.intent_classifier import classify_intent_sync


@pytest.fixture(autouse=True)
def _no_redis(monkeypatch):
    monkeypatch.setattr(semantic_cache, "_redis_available", False)


def _rate_limited():
    return litellm.RateLimitError(message="tokens per minute", llm_provider="groq", model="groq/openai/gpt-oss-20b")


def _patch_llm(side_effect, target="orchestrator.intent_classifier.litellm.acompletion"):
    return patch(target, AsyncMock(side_effect=side_effect))


@pytest.mark.parametrize("error", [
    _rate_limited(),
    litellm.Timeout(message="timed out", model="groq/openai/gpt-oss-20b", llm_provider="groq"),
    ConnectionError("groq unreachable"),
])
def test_unavailable_llm_degrades_without_retrying(error):
    with _patch_llm(error) as llm:
        intent = classify_intent_sync("90s crime movies")
    assert llm.call_count == 1                      # retrying a rate limit immediately just fails again
    assert intent.degraded and intent.primary_intent == "search"
    e = intent.entities
    assert e.hard_filters and e.genres == ["crime"] and (e.year_from, e.year_to) == (1990, 1999)


def test_fallback_without_readable_filters_is_a_plain_search():
    with _patch_llm(_rate_limited()):
        intent = classify_intent_sync("batman")
    assert intent.degraded and not intent.entities.hard_filters
    assert intent.interpreted_as == "batman"


def test_malformed_output_is_still_retried_once():
    bad = litellm.BadRequestError(message="tool_use_failed", model="m", llm_provider="groq")
    with _patch_llm(bad) as llm:
        intent = classify_intent_sync("tamil thrillers")
    assert llm.call_count == 2
    assert intent.degraded and intent.entities.language == "ta"


def test_failed_synthesis_still_returns_results():
    movie = {"movie_id": 1, "title": "Heat", "vote_average": 8.3, "release_date": "1995-12-15"}
    intent = QueryIntent(primary_intent="discover", interpreted_as="crime")
    with _patch_llm(_rate_limited(), "orchestrator.aggregator.litellm.acompletion"):
        results, synthesis = asyncio.run(aggregate(
            {"discover": [movie]}, intent, "crime movies", include_synthesis=True, include_providers=False,
        ))
    assert [r.title for r in results] == ["Heat"]
    assert synthesis is None


def test_degraded_responses_are_flagged_and_never_cached(monkeypatch):
    monkeypatch.setattr(app_mod, "guess_plan", lambda *a, **k: None)
    monkeypatch.setattr(app_mod._engine, "run", AsyncMock(return_value={"_services_invoked": []}))

    async def ask():
        return await app_mod.query_endpoint(QueryRequest(q="degraded-cache-test 90s crime"), authorization=None)

    with _patch_llm(_rate_limited()) as llm:
        first = asyncio.run(ask())
        second = asyncio.run(ask())
    assert first.meta.degraded and not second.meta.cache_hit
    assert llm.call_count == 2                      # the LLM is asked again once it may be back


@pytest.mark.parametrize("query", ["star wars", "the french connection", "2001 a space odyssey", "a history of violence"])
def test_fallback_does_not_enforce_filter_words_inside_titles(query):
    # Enforcing genre=war on "star wars" (or year=2001 on the 1968 film) would filter the title out
    with _patch_llm(_rate_limited()):
        intent = classify_intent_sync(query)
    e = intent.entities
    assert intent.degraded and not e.hard_filters
    assert not (e.genres or e.language or e.year_from)
