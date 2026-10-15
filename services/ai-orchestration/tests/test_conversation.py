"""Tests for conversational follow-ups and the streamed pipeline — the LLM, TMDB and providers
are mocked, so no API key or network is needed.
Run with:  pytest services/ai-orchestration/tests -v
"""
import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, patch

import litellm
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app as app_mod
import cache.semantic_cache as semantic_cache
import orchestrator.aggregator as aggregator
from models.intent import QueryEntities, QueryIntent
from models.query import ConversationState, MovieResult, QueryOptions, QueryRequest
from orchestrator.intent_classifier import classify_intent, merge_entities


@pytest.fixture(autouse=True)
def _empty_cache(monkeypatch):
    monkeypatch.setattr(semantic_cache, "_redis_available", False)
    monkeypatch.setattr(semantic_cache, "_store", {})
    monkeypatch.setattr(semantic_cache, "_access", {})


def _thrillers_like_se7en(shown=(), turn=1):
    return ConversationState(
        query="thrillers like se7en",
        intent="find_similar",
        interpreted_as="Movies similar to Se7en — thriller",
        entities=QueryEntities(seed_movies=["Se7en"], genres=["thriller"]),
        shown_ids=list(shown),
        turn=turn,
    )


def _llm_returning(arguments: dict):
    """An acompletion mock whose forced function call returns `arguments`."""
    call = type("Call", (), {"function": type("F", (), {"arguments": json.dumps(arguments)})()})()
    message = type("Message", (), {"tool_calls": [call]})()
    response = type("Response", (), {"choices": [type("Choice", (), {"message": message})()]})()
    return AsyncMock(return_value=response)


def _movie(mid, title, year=2001, **extra):
    return {"movie_id": mid, "title": title, "release_date": f"{year}-01-01", "vote_average": 7.5, **extra}


# ── Merging a follow-up into the previous search ──────────────────────────────

class TestMergeEntities:

    def test_constraints_the_follow_up_leaves_out_are_kept(self):
        merged = merge_entities(
            QueryEntities(genres=["thriller"], language="ko"),
            QueryEntities(platforms=["Netflix"]),
        )
        assert (merged.genres, merged.language, merged.platforms) == (["thriller"], "ko", ["Netflix"])

    def test_follow_up_values_replace_previous_ones(self):
        merged = merge_entities(QueryEntities(language="ko"), QueryEntities(language="hi"))
        assert merged.language == "hi"

    def test_removed_constraints_are_dropped(self):
        merged = merge_entities(
            QueryEntities(genres=["thriller"], language="ko", year_from=1990, year_to=1999),
            QueryEntities(),
            removed=["language", "years"],
        )
        assert merged.genres == ["thriller"]
        assert merged.language is None and merged.year_from is None and merged.year_to is None

    def test_a_year_range_is_replaced_as_a_whole(self):
        merged = merge_entities(QueryEntities(year_from=1990, year_to=1999), QueryEntities(year_from=2015))
        assert (merged.year_from, merged.year_to) == (2015, None)


# ── Classifying a follow-up ───────────────────────────────────────────────────

class TestFollowUpClassification:

    def test_refinement_keeps_the_previous_search_and_enforces_the_platform(self):
        llm = _llm_returning({
            "primary_intent": "find_similar", "refines_previous": True, "platforms": ["Netflix"],
            "interpreted_as": "Thrillers like Se7en on Netflix",
        })
        with patch("orchestrator.intent_classifier.litellm.acompletion", llm):
            intent = asyncio.run(classify_intent("only on netflix", previous=_thrillers_like_se7en()))

        e = intent.entities
        assert intent.refines_previous and intent.primary_intent == "find_similar"
        assert e.seed_movies == ["Se7en"] and e.genres == ["thriller"]
        assert e.platforms == ["Netflix"] and e.explicit_platforms
        # The LLM saw the previous search and was offered the follow-up fields
        kwargs = llm.call_args.kwargs
        assert "Se7en" in kwargs["messages"][0]["content"]
        assert "refines_previous" in kwargs["tools"][0]["function"]["parameters"]["properties"]

    def test_a_filter_added_in_a_follow_up_is_enforced(self):
        llm = _llm_returning({
            "primary_intent": "find_similar", "refines_previous": True, "language": "hi",
            "interpreted_as": "Hindi thrillers like Se7en",
        })
        with patch("orchestrator.intent_classifier.litellm.acompletion", llm):
            intent = asyncio.run(classify_intent("in hindi", previous=_thrillers_like_se7en()))
        assert intent.entities.language == "hi" and intent.entities.hard_filters

    def test_new_search_ignores_the_previous_one(self):
        llm = _llm_returning({"primary_intent": "search", "refines_previous": False, "interpreted_as": "Batman"})
        with patch("orchestrator.intent_classifier.litellm.acompletion", llm):
            intent = asyncio.run(classify_intent("batman", previous=_thrillers_like_se7en()))
        assert not intent.refines_previous
        assert intent.entities.seed_movies == [] and intent.entities.genres == []

    def test_first_queries_are_not_offered_follow_up_fields(self):
        llm = _llm_returning({"primary_intent": "search", "interpreted_as": "Batman"})
        with patch("orchestrator.intent_classifier.litellm.acompletion", llm):
            asyncio.run(classify_intent("batman"))
        properties = llm.call_args.kwargs["tools"][0]["function"]["parameters"]["properties"]
        assert "refines_previous" not in properties


class TestFollowUpWithoutLLM:

    @staticmethod
    def _classify_offline(query):
        down = AsyncMock(side_effect=litellm.RateLimitError(message="rate", llm_provider="groq", model="m"))
        with patch("orchestrator.intent_classifier.litellm.acompletion", down):
            return asyncio.run(classify_intent(query, previous=_thrillers_like_se7en()))

    def test_a_filter_message_refines_the_previous_search(self):
        intent = self._classify_offline("only hindi ones")
        assert intent.degraded and intent.refines_previous
        assert intent.primary_intent == "find_similar"
        assert intent.entities.language == "hi" and intent.entities.seed_movies == ["Se7en"]

    def test_a_platform_message_refines_the_previous_search(self):
        intent = self._classify_offline("only on netflix")
        assert intent.entities.platforms == ["Netflix"] and intent.entities.explicit_platforms

    def test_asking_for_more_excludes_what_was_shown(self):
        intent = self._classify_offline("show me more")
        assert intent.refines_previous and intent.exclude_shown

    def test_anything_else_is_a_new_search(self):
        intent = self._classify_offline("batman")
        assert not intent.refines_previous and intent.primary_intent == "search"

    def test_a_title_containing_a_filter_word_is_a_new_search(self):
        # "wars" reads as the war genre, but the message names a movie of its own
        intent = self._classify_offline("what about star wars")
        assert not intent.refines_previous and intent.entities.genres == []


# ── The pipeline: conversation state and streaming ────────────────────────────

def _run(request):
    async def collect():
        return [event async for event in app_mod._run_query(request, None)]
    return asyncio.run(collect())


class TestConversationPipeline:

    def test_show_me_more_skips_shown_movies_and_carries_the_conversation(self, monkeypatch):
        movies = [_movie(i, f"Movie {i}") for i in range(1, 7)]
        monkeypatch.setattr(app_mod._engine, "run", AsyncMock(return_value={"tmdb_sim": movies}))
        more = QueryIntent(
            primary_intent="find_similar", interpreted_as="More thrillers like Se7en",
            entities=QueryEntities(seed_movies=["Se7en"]), refines_previous=True, exclude_shown=True,
        )
        monkeypatch.setattr(app_mod, "classify_intent", AsyncMock(return_value=more))

        request = QueryRequest(
            q="show me more", conversation=_thrillers_like_se7en(shown=[1, 2, 3], turn=2),
            options=QueryOptions(max_results=3, include_providers=False),
        )
        response = dict(_run(request))["done"]

        assert [r.movie_id for r in response.results] == [4, 5, 6]
        assert response.conversation.shown_ids == [1, 2, 3, 4, 5, 6]
        assert response.conversation.turn == 3

    def test_a_new_search_starts_a_new_conversation(self, monkeypatch):
        monkeypatch.setattr(app_mod._engine, "run", AsyncMock(return_value={"search": [_movie(9, "Batman")]}))
        new = QueryIntent(primary_intent="search", interpreted_as="Batman")
        monkeypatch.setattr(app_mod, "classify_intent", AsyncMock(return_value=new))

        request = QueryRequest(
            q="conversation-test batman", conversation=_thrillers_like_se7en(shown=[1, 2]),
            options=QueryOptions(include_providers=False),
        )
        conversation = dict(_run(request))["done"].conversation
        assert conversation.shown_ids == [9] and conversation.turn == 1

    def test_the_same_follow_up_after_different_searches_is_not_shared_in_cache(self, monkeypatch):
        monkeypatch.setattr(app_mod._engine, "run", AsyncMock(return_value={}))
        classify = AsyncMock(return_value=QueryIntent(primary_intent="search", interpreted_as="x"))
        monkeypatch.setattr(app_mod, "classify_intent", classify)

        for previous_query in ("cache-test thrillers", "cache-test comedies"):
            previous = _thrillers_like_se7en().model_copy(update={"query": previous_query})
            _run(QueryRequest(q="only on netflix", conversation=previous))
        assert classify.call_count == 2


class TestStreaming:

    def test_events_arrive_in_pipeline_order(self, monkeypatch):
        monkeypatch.setattr(app_mod._engine, "run", AsyncMock(return_value={"discover": [_movie(1, "Heat")]}))
        monkeypatch.setattr(app_mod, "classify_intent", AsyncMock(
            return_value=QueryIntent(primary_intent="discover", interpreted_as="Crime movies"),
        ))
        monkeypatch.setattr(aggregator, "fetch_providers", AsyncMock(return_value={
            1: [{"name": "Netflix", "type": "flatrate"}],
        }))
        monkeypatch.setattr(aggregator, "_synthesise", AsyncMock(return_value="Heat leads the pack."))

        request = QueryRequest(q="stream-order crime", options=QueryOptions(include_synthesis=True))
        events = _run(request)

        assert [name for name, _ in events] == ["intent", "preview", "results", "synthesis", "done"]
        data = dict(events)
        assert data["preview"]["results"][0].providers == []
        assert data["results"]["results"][0].providers[0].name == "Netflix"
        assert data["done"].synthesis == "Heat leads the pack."

    def test_synthesis_runs_alongside_the_provider_fetch(self, monkeypatch):
        """Providers can't change which movies are shown here, so the summary needn't wait for them."""
        synthesis_started = asyncio.Event()

        async def synthesise(*args):
            synthesis_started.set()
            return "summary"

        async def providers(*args, **kwargs):
            await asyncio.wait_for(synthesis_started.wait(), timeout=1)   # times out if run in sequence
            return {}

        monkeypatch.setattr(aggregator, "_synthesise", synthesise)
        monkeypatch.setattr(aggregator, "fetch_providers", providers)
        intent = QueryIntent(primary_intent="discover", interpreted_as="crime")

        results, synthesis = asyncio.run(aggregator.aggregate(
            {"discover": [_movie(1, "Heat")]}, intent, "crime", include_synthesis=True,
        ))
        assert synthesis == "summary" and [r.title for r in results] == ["Heat"]

    def test_platform_filtered_results_are_not_previewed(self, monkeypatch):
        """Before providers are known, a preview would show movies the platform filter then removes."""
        monkeypatch.setattr(aggregator, "fetch_providers", AsyncMock(return_value={
            1: [{"name": "Netflix", "type": "flatrate"}], 2: [{"name": "Hulu", "type": "flatrate"}],
        }))
        intent = QueryIntent(
            primary_intent="discover", interpreted_as="crime on netflix",
            entities=QueryEntities(platforms=["Netflix"], explicit_platforms=True),
        )

        async def stages():
            return [s async for s in aggregator.aggregate_stream(
                {"discover": [_movie(1, "Heat"), _movie(2, "Ronin")]}, intent, "crime",
            )]
        events = asyncio.run(stages())
        assert [name for name, _ in events] == ["results", "synthesis"]
        assert [r.title for r in events[0][1]] == ["Heat"]

    def test_stream_endpoint_sends_server_sent_events(self, monkeypatch):
        from fastapi.testclient import TestClient

        monkeypatch.setattr(app_mod._engine, "run", AsyncMock(return_value={"discover": [_movie(1, "Heat")]}))
        monkeypatch.setattr(app_mod, "classify_intent", AsyncMock(
            return_value=QueryIntent(primary_intent="discover", interpreted_as="Crime movies"),
        ))
        response = TestClient(app_mod.app).post("/api/query/stream", json={   # no lifespan: skips index warm-up
            "q": "sse-test crime", "options": {"include_providers": False},
        })

        assert response.headers["content-type"].startswith("text/event-stream")
        blocks = [b for b in response.text.split("\n\n") if b.strip()]
        names = [b.split("\n")[0].removeprefix("event: ") for b in blocks]
        assert names == ["intent", "results", "done"]
        done = json.loads(blocks[-1].split("\n")[1].removeprefix("data: "))
        assert done["conversation"]["shown_ids"] == [1]
