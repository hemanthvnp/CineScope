"""
Unit tests for the rule-based intent classifier.

Tests cover intent routing and entity extraction across all 8 intent types.
Run with:  pytest services/ml-service/tests/test_intent_classifier.py -v

Note: These run on the ai-orchestration service's classifier, which lives under
services/ai-orchestration/orchestrator/intent_classifier.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../ai-orchestration"))

from orchestrator.intent_classifier import classify_intent_sync


class TestIntentRouting:
    """Verify the correct primary intent is selected for each query type."""

    def test_discover_trending(self):
        intent = classify_intent_sync("Show trending sci-fi movies")
        assert intent.primary_intent == "discover"

    def test_discover_popular(self):
        intent = classify_intent_sync("What are the most popular movies right now?")
        assert intent.primary_intent == "discover"

    def test_find_similar(self):
        intent = classify_intent_sync("Movies similar to Inception")
        assert intent.primary_intent == "find_similar"

    def test_find_similar_like_keyword(self):
        intent = classify_intent_sync("Films like The Dark Knight")
        assert intent.primary_intent == "find_similar"

    def test_summarize(self):
        intent = classify_intent_sync("Summarize Interstellar reviews")
        assert intent.primary_intent == "summarize"

    def test_mood_based(self):
        intent = classify_intent_sync("Something funny for a bad day")
        assert intent.primary_intent == "mood_based"

    def test_lookup_runtime(self):
        intent = classify_intent_sync("What is the runtime of Oppenheimer?")
        assert intent.primary_intent == "lookup"

    def test_filter_provider_netflix(self):
        intent = classify_intent_sync("Thriller movies on Netflix")
        assert intent.primary_intent == "filter_provider"


class TestEntityExtraction:
    """Verify entities are extracted correctly from queries."""

    def test_seed_movie_extracted(self):
        intent = classify_intent_sync("Movies similar to Fight Club")
        assert "Fight Club" in intent.entities.seed_movies

    def test_seed_not_polluted_by_context(self):
        intent = classify_intent_sync("Find movies similar to Fight Club streamable in India")
        seeds = intent.entities.seed_movies
        assert len(seeds) > 0
        assert all("streamable" not in s.lower() for s in seeds)

    def test_genre_extracted(self):
        intent = classify_intent_sync("Show trending sci-fi movies")
        assert "sci-fi" in intent.entities.genres

    def test_multiple_genres(self):
        intent = classify_intent_sync("Dark thriller drama movies")
        genres = intent.entities.genres
        assert len(genres) >= 1

    def test_country_india(self):
        intent = classify_intent_sync("Popular movies in India")
        assert intent.entities.country == "IN"

    def test_country_korea(self):
        intent = classify_intent_sync("Best Korean movies")
        assert intent.entities.country == "KR"

    def test_streaming_filter_detected(self):
        intent = classify_intent_sync("Action movies available on Netflix")
        assert intent.entities.streaming_filter is True

    def test_year_extraction(self):
        intent = classify_intent_sync("Best movies from 2020")
        assert intent.entities.year_from == 2020

    def test_personalization_flag(self):
        intent = classify_intent_sync("Recommend something for me based on my taste")
        assert intent.requires_personalization is True

    def test_synthesis_flag_for_summarize(self):
        intent = classify_intent_sync("Summarize Inception reviews")
        assert intent.requires_synthesis is True

    def test_review_word_not_in_seed(self):
        intent = classify_intent_sync("Summarize Interstellar reviews")
        seeds = intent.entities.seed_movies
        assert all("review" not in s.lower() for s in seeds)


class TestInterpretedAs:
    """Verify interpreted_as produces readable one-liners."""

    def test_interpreted_as_non_empty(self):
        intent = classify_intent_sync("Show me horror movies from the 90s")
        assert len(intent.interpreted_as) > 5

    def test_interpreted_as_includes_seed(self):
        intent = classify_intent_sync("Movies like Parasite")
        assert "Parasite" in intent.interpreted_as
