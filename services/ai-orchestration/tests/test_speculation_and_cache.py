"""Unit tests for speculative prefetch, the intent cache key and in-flight coalescing.
No network or LLM needed.
Run with:  pytest services/ai-orchestration/tests -v
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cache.semantic_cache as semantic_cache
from app import _intent_cache_key
from cache.semantic_cache import make_tool_key
from models.intent import ExecutionPlan, PlanNode, QueryEntities, QueryIntent
from models.query import QueryFilters, QueryRequest
from orchestrator.execution_engine import ExecutionEngine
from orchestrator.rule_parser import parse_entities
from orchestrator.speculator import guess_plan
from orchestrator.tool_planner import build_plan
from tools.registry import TOOL_REGISTRY


@pytest.fixture(autouse=True)
def _no_redis(monkeypatch):
    monkeypatch.setattr(semantic_cache, "_redis_available", False)


def _llm_intent(primary: str, **entities) -> QueryIntent:
    """An intent shaped like the classifier's output, with LLM-style spellings."""
    intent = QueryIntent(primary_intent=primary, interpreted_as=f"llm wording for {primary}",
                         entities=QueryEntities(**entities))
    intent.entities.hard_filters = primary != "find_similar"
    return intent


def _keys(plan: ExecutionPlan, tool: str) -> set:
    return {make_tool_key(n.tool, n.params) for n in plan.nodes if n.tool == tool}


# ── Rule-based parse ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("query, expected", [
    ("90s sci-fi movies", {"genres": ["sci-fi"], "year_from": 1990, "year_to": 1999}),
    ("sci fi movies of the nineties", {"genres": ["sci-fi"], "year_from": 1990, "year_to": 1999}),
    ("Best Tamil thriller movies!", {"genres": ["thriller"], "language": "ta"}),
    ("horror films from 2014", {"genres": ["horror"], "year_from": 2014, "year_to": 2014}),
    ("2010s romantic comedies", {"genres": ["comedy", "romance"], "year_from": 2010, "year_to": 2019}),
    ("french dramas rated above 8", {"genres": ["drama"], "language": "fr", "min_rating": 8.0}),
])
def test_parse_entities(query, expected):
    e = parse_entities(query).model_dump()
    for field, value in expected.items():
        assert e[field] == value, field


def test_relative_years_are_left_to_the_llm():
    e = parse_entities("horror movies after 2015")
    assert e.year_from is None and e.year_to is None


def test_no_guess_without_unambiguous_signals():
    assert guess_plan("inception") is None
    assert guess_plan("something to cheer me up") is None


# ── The guess must match the real plan, or the prefetch is wasted ────────────

@pytest.mark.parametrize("primary", ["discover", "search", "recommend", "mood_based", "filter_provider"])
def test_guess_matches_llm_plan_for_every_filtered_intent(primary):
    guess = guess_plan("90s sci-fi movies")
    llm = build_plan(_llm_intent(primary, genres=["Science Fiction"], year_from=1990, year_to=1999),
                     user_id="u1" if primary == "recommend" else None)
    assert _keys(guess, "tmdb_discover")
    assert _keys(guess, "tmdb_discover") <= _keys(llm, "tmdb_discover")


def test_guess_includes_explicit_filters():
    filters = QueryFilters(language="hi", min_rating=7)
    guess = guess_plan("action movies", filters)
    intent = _llm_intent("discover", genres=["Action"], language="hi", min_rating=7)
    assert _keys(guess, "tmdb_discover") == _keys(build_plan(intent), "tmdb_discover")


def test_find_similar_seed_stops_at_but():
    resolve = {n.id: n.params for n in guess_plan("movies like the dark knight but funnier").nodes}["resolve_seed"]
    assert resolve["query"] == "the dark knight"


def test_find_similar_guess_matches_seed_resolution():
    guess = guess_plan("Movies like Inception")
    llm = build_plan(_llm_intent("find_similar", seed_movies=["Inception"], genres=["sci-fi"]))
    resolve = {n.id: n.params for n in llm.nodes}["resolve_seed"]
    assert {n.id: n.params for n in guess.nodes}["resolve_seed"] == resolve
    assert {n.id for n in guess.nodes} == {"resolve_seed", "tmdb_sim"}


# ── Intent cache key ──────────────────────────────────────────────────────────

def _intent_key(intent: QueryIntent, q: str = "x", **options) -> str:
    request = QueryRequest(q=q, options=options)
    plan = build_plan(intent)
    return _intent_cache_key(plan, intent, request, "anon",
                             request.options.include_synthesis or intent.requires_synthesis)


def test_paraphrases_share_an_intent_key():
    a = _llm_intent("discover", genres=["sci-fi"], year_from=1990, year_to=1999)
    b = _llm_intent("discover", genres=["Science Fiction"], year_from=1990, year_to=1999)
    b.interpreted_as = "Science fiction from the nineties"
    assert _intent_key(a, "90s sci-fi") == _intent_key(b, "science fiction movies from the 1990s")


def test_different_meaning_or_options_get_different_keys():
    base = _llm_intent("discover", genres=["sci-fi"], year_from=1990, year_to=1999)
    other_years = _llm_intent("discover", genres=["sci-fi"], year_from=1980, year_to=1989)
    assert _intent_key(base) != _intent_key(other_years)
    assert _intent_key(base) != _intent_key(base, max_results=20)


def test_synthesised_answers_are_only_shared_by_identical_queries():
    runtime = _llm_intent("lookup", seed_movies=["Inception"])
    director = _llm_intent("lookup", seed_movies=["Inception"])
    assert _intent_key(runtime, "inception runtime") != _intent_key(director, "who directed inception")
    assert _intent_key(runtime, "Inception runtime?") == _intent_key(director, "inception runtime")


def test_search_queries_with_no_entities_do_not_collide():
    batman = QueryIntent(primary_intent="search", interpreted_as="Batman")
    superman = QueryIntent(primary_intent="search", interpreted_as="Superman")
    assert _intent_key(batman) != _intent_key(superman)


# ── In-flight coalescing ──────────────────────────────────────────────────────

def test_identical_concurrent_calls_share_one_tool_call(monkeypatch):
    calls = []

    async def slow_tool(params):
        calls.append(params)
        await asyncio.sleep(0.05)
        return [{"movie_id": 1}]

    monkeypatch.setitem(TOOL_REGISTRY, "fake_tool", {"fn": slow_tool, "circuit_breaker": "fake"})
    node = PlanNode(id="n", tool="fake_tool", params={"q": "coalesce-test"})

    async def scenario():
        engine = ExecutionEngine()
        engine.prefetch(ExecutionPlan(nodes=[node]))   # speculative call starts first
        await asyncio.sleep(0)
        return await engine.run(ExecutionPlan(nodes=[node]))

    result = asyncio.run(scenario())
    assert result["n"] == [{"movie_id": 1}]
    assert len(calls) == 1
