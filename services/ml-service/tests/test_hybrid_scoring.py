"""
Unit tests for the hybrid recommender's scoring and utility functions.

These test pure logic: quality scoring, quality floor checks, era parsing,
and strategy selection — all without hitting MongoDB or TMDB.

Run with:  pytest services/ml-service/tests/test_hybrid_scoring.py -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from recommender.hybrid import (
    _compute_quality_score,
    _passes_quality_floor,
    _parse_era,
    _get_movie_year,
    _safe_float,
    _determine_strategy,
)


class TestQualityScore:
    """Quality score = 0.60×rating_norm + 0.25×confidence + 0.15×popularity_norm"""

    def test_perfect_movie(self):
        movie = {"vote_average": 10.0, "vote_count": 5000, "popularity": 500}
        score = _compute_quality_score(movie)
        assert score == 1.0

    def test_zero_for_empty_movie(self):
        assert _compute_quality_score({}) == 0.0
        assert _compute_quality_score(None) == 0.0

    def test_score_bounded_0_to_1(self):
        movie = {"vote_average": 8.5, "vote_count": 1200, "popularity": 250}
        score = _compute_quality_score(movie)
        assert 0.0 <= score <= 1.0

    def test_higher_rated_scores_higher(self):
        high = {"vote_average": 9.0, "vote_count": 500, "popularity": 100}
        low  = {"vote_average": 5.0, "vote_count": 500, "popularity": 100}
        assert _compute_quality_score(high) > _compute_quality_score(low)

    def test_more_votes_increase_confidence(self):
        few   = {"vote_average": 8.0, "vote_count": 10,  "popularity": 100}
        many  = {"vote_average": 8.0, "vote_count": 1000, "popularity": 100}
        assert _compute_quality_score(many) > _compute_quality_score(few)


class TestQualityFloor:
    """Standard floor: vote_avg >= 6.0 and vote_count >= 80."""

    def test_passes_when_above_floor(self):
        movie = {"vote_average": 7.5, "vote_count": 200}
        assert _passes_quality_floor(movie) is True

    def test_fails_low_rating(self):
        movie = {"vote_average": 5.0, "vote_count": 200}
        assert _passes_quality_floor(movie) is False

    def test_fails_low_count(self):
        movie = {"vote_average": 8.0, "vote_count": 30}
        assert _passes_quality_floor(movie) is False

    def test_regional_relaxed_vote_count(self):
        # Regional relaxes vote_count floor (80 → 30), avg stays at 6.0
        movie = {"vote_average": 6.5, "vote_count": 40}
        assert _passes_quality_floor(movie, is_regional=True) is True

    def test_regional_still_fails_very_low(self):
        movie = {"vote_average": 3.0, "vote_count": 5}
        assert _passes_quality_floor(movie, is_regional=True) is False

    def test_none_movie_fails(self):
        assert _passes_quality_floor(None) is False


class TestEraParsing:
    """_parse_era converts human era strings into (start_year, end_year) tuples."""

    def test_decade_format(self):
        assert _parse_era("1990s") == (1990, 1999)

    def test_range_format(self):
        assert _parse_era("2000-2010") == (2000, 2010)

    def test_alias_classic(self):
        start, end = _parse_era("classic")
        assert start < 1970

    def test_alias_modern(self):
        start, end = _parse_era("modern")
        assert start >= 2010

    def test_alias_90s(self):
        assert _parse_era("90s") == (1990, 1999)

    def test_none_returns_none(self):
        assert _parse_era(None) is None

    def test_empty_returns_none(self):
        assert _parse_era("") is None


class TestStrategySelection:
    """_determine_strategy picks the right recommendation pathway."""

    def test_hybrid_when_enough_ratings_and_collab_ready(self):
        # Simulate collaborative model built by patching
        import recommender.collaborative as collab
        original = collab.is_model_built
        collab.is_model_built = lambda: True
        try:
            strategy = _determine_strategy(
                has_ratings=True, has_prefs=True, has_enough_for_collab=True
            )
            assert strategy == "hybrid"
        finally:
            collab.is_model_built = original

    def test_content_only_when_few_ratings(self):
        strategy = _determine_strategy(
            has_ratings=True, has_prefs=True, has_enough_for_collab=False
        )
        assert strategy == "content_only"

    def test_genre_fallback_no_ratings_has_prefs(self):
        strategy = _determine_strategy(
            has_ratings=False, has_prefs=True, has_enough_for_collab=False
        )
        assert strategy == "genre_fallback"

    def test_trending_fallback_cold_start(self):
        strategy = _determine_strategy(
            has_ratings=False, has_prefs=False, has_enough_for_collab=False
        )
        assert strategy == "trending_fallback"


class TestSafeFloat:
    def test_valid_float(self):
        assert _safe_float(7.5) == 7.5

    def test_string_number(self):
        assert _safe_float("8.2") == 8.2

    def test_none_returns_default(self):
        assert _safe_float(None) == 0.0

    def test_invalid_string_returns_default(self):
        assert _safe_float("abc", default=1.0) == 1.0
