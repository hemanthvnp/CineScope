"""Unit tests for structured filters — no network or LLM needed.
Run with:  pytest services/ai-orchestration/tests -v
"""
import os
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.intent import QueryIntent
from models.query import QueryFilters, QueryRequest
from orchestrator.aggregator import _matches_filters, _on_platform
from orchestrator.intent_classifier import apply_filters, filter_only_intent
from orchestrator.tool_planner import build_plan
from tools.tmdb_tool import genre_ids


def test_request_needs_query_or_filters():
    with pytest.raises(ValidationError):
        QueryRequest(q="")
    assert QueryRequest(q="", filters={"language": "hi"}).filters.language == "hi"
    assert QueryRequest(q="inception").filters is None


def test_year_range_resolution():
    assert QueryFilters(year=2014).year_range() == (2014, 2014)
    assert QueryFilters(era="Modern").year_range() == (2000, 2015)
    assert QueryFilters(era="Modern", year_from=2010).year_range() == (2010, 2015)
    assert QueryFilters().year_range() == (None, None)


def test_genre_ids_accepts_names_and_ids():
    assert genre_ids(["Action", "53", "sci-fi", "nonsense"]) == [28, 53, 878]


def _combined():
    f = QueryFilters(genres=["28", "thriller"], language="hi", era="Modern", min_rating=7)
    return f, apply_filters(filter_only_intent(f), f)


def test_combined_filters_become_hard_constraints_and_discover_node():
    _, intent = _combined()
    assert intent.entities.hard_filters
    discover = next(n for n in build_plan(intent).nodes if n.tool == "tmdb_discover")
    assert discover.params["language"] == "hi"
    assert (discover.params["year_from"], discover.params["year_to"]) == (2000, 2015)
    assert discover.params["min_rating"] == 7


def test_explicit_filter_overrides_llm_entities():
    intent = QueryIntent(primary_intent="search", interpreted_as="x")
    intent.entities.year_from = intent.entities.year_to = 1999
    intent = apply_filters(intent, QueryFilters(year=2014))
    assert intent.entities.year_from == 2014


def test_matches_filters():
    _, intent = _combined()
    movie = {"genre_ids": [28, 53], "original_language": "hi", "release_date": "2010-05-01", "vote_average": 7.5}
    assert _matches_filters(movie, intent.entities)
    for override in ({"genre_ids": [28]}, {"original_language": "en"},
                     {"release_date": "2020-01-01"}, {"vote_average": 6.0}):
        assert not _matches_filters({**movie, **override}, intent.entities)


def test_missing_fields_do_not_disqualify():
    _, intent = _combined()
    assert _matches_filters({"movie_id": 1}, intent.entities)


def test_platform_matching():
    assert _on_platform([{"name": "Disney Plus"}], ["Disney+"])
    assert not _on_platform([{"name": "Netflix"}], ["Prime Video"])
    assert _on_platform([{"name": "Netflix"}], [])
    assert not _on_platform([], ["Netflix"])
