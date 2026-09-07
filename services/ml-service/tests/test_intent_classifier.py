"""
Unit tests for the intent classifier — litellm.acompletion is mocked so no API key needed.
Tests verify that classify_intent_sync correctly unpacks tool-call JSON into QueryIntent.
Run with:  pytest services/ml-service/tests/test_intent_classifier.py -v
"""
import json
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../ai-orchestration"))

from orchestrator.intent_classifier import classify_intent_sync


def _fake_response(primary_intent: str, **kwargs) -> MagicMock:
    args = {"primary_intent": primary_intent, "interpreted_as": f"query -> {primary_intent}", **kwargs}
    tool_call = MagicMock()
    tool_call.function.arguments = json.dumps(args)
    message = MagicMock()
    message.tool_calls = [tool_call]
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


def _patch_groq(response: MagicMock):
    return patch(
        "orchestrator.intent_classifier.litellm.acompletion",
        AsyncMock(return_value=response),
    )


class TestIntentRouting:

    def test_discover_trending(self):
        with _patch_groq(_fake_response("discover", genres=["sci-fi"])):
            intent = classify_intent_sync("Show trending sci-fi movies")
        assert intent.primary_intent == "discover"

    def test_discover_popular(self):
        with _patch_groq(_fake_response("discover")):
            intent = classify_intent_sync("What are the most popular movies right now?")
        assert intent.primary_intent == "discover"

    def test_find_similar(self):
        with _patch_groq(_fake_response("find_similar", seed_movies=["Inception"])):
            intent = classify_intent_sync("Movies similar to Inception")
        assert intent.primary_intent == "find_similar"

    def test_find_similar_like_keyword(self):
        with _patch_groq(_fake_response("find_similar", seed_movies=["The Dark Knight"])):
            intent = classify_intent_sync("Films like The Dark Knight")
        assert intent.primary_intent == "find_similar"

    def test_summarize(self):
        with _patch_groq(_fake_response("summarize", requires_synthesis=True)):
            intent = classify_intent_sync("Summarize Interstellar reviews")
        assert intent.primary_intent == "summarize"

    def test_mood_based(self):
        with _patch_groq(_fake_response("mood_based", mood="funny")):
            intent = classify_intent_sync("Something funny for a bad day")
        assert intent.primary_intent == "mood_based"

    def test_lookup_runtime(self):
        with _patch_groq(_fake_response("lookup")):
            intent = classify_intent_sync("What is the runtime of Oppenheimer?")
        assert intent.primary_intent == "lookup"

    def test_filter_provider_netflix(self):
        with _patch_groq(_fake_response("filter_provider", platforms=["Netflix"])):
            intent = classify_intent_sync("Thriller movies on Netflix")
        assert intent.primary_intent == "filter_provider"


class TestEntityExtraction:

    def test_seed_movie_extracted(self):
        with _patch_groq(_fake_response("find_similar", seed_movies=["Fight Club"])):
            intent = classify_intent_sync("Movies similar to Fight Club")
        assert "Fight Club" in intent.entities.seed_movies

    def test_seed_not_polluted_by_context(self):
        with _patch_groq(_fake_response("find_similar", seed_movies=["Fight Club"])):
            intent = classify_intent_sync("Find movies similar to Fight Club streamable in India")
        seeds = intent.entities.seed_movies
        assert len(seeds) > 0
        assert all("streamable" not in s.lower() for s in seeds)

    def test_genre_extracted(self):
        with _patch_groq(_fake_response("discover", genres=["sci-fi"])):
            intent = classify_intent_sync("Show trending sci-fi movies")
        assert "sci-fi" in intent.entities.genres

    def test_multiple_genres(self):
        with _patch_groq(_fake_response("search", genres=["thriller", "drama"])):
            intent = classify_intent_sync("Dark thriller drama movies")
        assert len(intent.entities.genres) >= 1

    def test_country_india(self):
        with _patch_groq(_fake_response("discover", country="IN")):
            intent = classify_intent_sync("Popular movies in India")
        assert intent.entities.country == "IN"

    def test_country_korea(self):
        with _patch_groq(_fake_response("discover", country="KR")):
            intent = classify_intent_sync("Best Korean movies")
        assert intent.entities.country == "KR"

    def test_streaming_filter_detected(self):
        with _patch_groq(_fake_response("filter_provider", platforms=["Netflix"])):
            intent = classify_intent_sync("Action movies available on Netflix")
        assert intent.entities.streaming_filter is True

    def test_year_extraction(self):
        with _patch_groq(_fake_response("discover", year_from=2020, year_to=2020)):
            intent = classify_intent_sync("Best movies from 2020")
        assert intent.entities.year_from == 2020

    def test_personalization_flag(self):
        with _patch_groq(_fake_response("recommend", requires_personalization=True)):
            intent = classify_intent_sync("Recommend something for me based on my taste")
        assert intent.requires_personalization is True

    def test_synthesis_flag_for_summarize(self):
        with _patch_groq(_fake_response("summarize", requires_synthesis=True)):
            intent = classify_intent_sync("Summarize Inception reviews")
        assert intent.requires_synthesis is True

    def test_review_word_not_in_seed(self):
        with _patch_groq(_fake_response("summarize", seed_movies=["Interstellar"])):
            intent = classify_intent_sync("Summarize Interstellar reviews")
        assert all("review" not in s.lower() for s in intent.entities.seed_movies)


class TestInterpretedAs:

    def test_interpreted_as_non_empty(self):
        with _patch_groq(_fake_response("discover", interpreted_as="Horror movies from the 90s")):
            intent = classify_intent_sync("Show me horror movies from the 90s")
        assert len(intent.interpreted_as) > 5

    def test_interpreted_as_includes_seed(self):
        with _patch_groq(_fake_response("find_similar", seed_movies=["Parasite"],
                                        interpreted_as="Movies similar to Parasite")):
            intent = classify_intent_sync("Movies like Parasite")
        assert "Parasite" in intent.interpreted_as
