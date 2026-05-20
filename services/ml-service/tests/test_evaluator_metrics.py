"""
Unit tests for offline evaluation metric functions.

These are pure functions with no I/O — fast and deterministic.
Run with:  pytest services/ml-service/tests/test_evaluator_metrics.py -v
"""
import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from recommender.evaluator import (
    _hit_at_k,
    _precision_at_k,
    _recall_at_k,
    _reciprocal_rank,
    _ndcg_at_k,
)


# ── Hit Rate@K ────────────────────────────────────────────────────────────────

class TestHitAtK:
    def test_hit_when_item_in_top_k(self):
        assert _hit_at_k([10, 20, 30, 40], held_out=20, k=3) == 1.0

    def test_miss_when_item_outside_k(self):
        assert _hit_at_k([10, 20, 30, 40], held_out=40, k=3) == 0.0

    def test_miss_when_item_not_in_list(self):
        assert _hit_at_k([10, 20, 30], held_out=99, k=5) == 0.0

    def test_hit_exactly_at_boundary(self):
        assert _hit_at_k([10, 20, 30], held_out=30, k=3) == 1.0

    def test_empty_list_returns_miss(self):
        assert _hit_at_k([], held_out=5, k=10) == 0.0


# ── Precision@K ───────────────────────────────────────────────────────────────

class TestPrecisionAtK:
    def test_perfect_precision(self):
        assert _precision_at_k([1, 2, 3], relevant={1, 2, 3}, k=3) == 1.0

    def test_zero_precision(self):
        assert _precision_at_k([4, 5, 6], relevant={1, 2, 3}, k=3) == 0.0

    def test_partial_precision(self):
        result = _precision_at_k([1, 5, 3, 6], relevant={1, 3}, k=4)
        assert result == 0.5  # 2 hits in top-4

    def test_k_larger_than_list(self):
        # k=10 but only 3 items: denominator is still k
        result = _precision_at_k([1, 2, 3], relevant={1, 2}, k=10)
        assert result == 0.2  # 2/10

    def test_empty_recommended_returns_zero(self):
        assert _precision_at_k([], relevant={1, 2}, k=5) == 0.0


# ── Recall@K ──────────────────────────────────────────────────────────────────

class TestRecallAtK:
    def test_perfect_recall(self):
        assert _recall_at_k([1, 2, 3], relevant={1, 2, 3}, k=3) == 1.0

    def test_zero_recall(self):
        assert _recall_at_k([4, 5], relevant={1, 2, 3}, k=2) == 0.0

    def test_partial_recall(self):
        result = _recall_at_k([1, 5, 3], relevant={1, 2, 3}, k=3)
        assert round(result, 4) == round(2 / 3, 4)

    def test_empty_relevant_returns_zero(self):
        assert _recall_at_k([1, 2, 3], relevant=set(), k=3) == 0.0


# ── MRR ───────────────────────────────────────────────────────────────────────

class TestReciprocalRank:
    def test_first_position(self):
        assert _reciprocal_rank([10, 20, 30], held_out=10) == 1.0

    def test_second_position(self):
        assert _reciprocal_rank([10, 20, 30], held_out=20) == 0.5

    def test_third_position(self):
        assert abs(_reciprocal_rank([10, 20, 30], held_out=30) - 1 / 3) < 1e-9

    def test_not_found_returns_zero(self):
        assert _reciprocal_rank([10, 20, 30], held_out=99) == 0.0

    def test_empty_list_returns_zero(self):
        assert _reciprocal_rank([], held_out=5) == 0.0


# ── NDCG@K ────────────────────────────────────────────────────────────────────

class TestNdcgAtK:
    def test_perfect_ranking(self):
        # Ideal: item 1 (score 1.0) at rank 1 — NDCG should be 1.0
        result = _ndcg_at_k([1], relevant_scores={1: 1.0}, k=1)
        assert abs(result - 1.0) < 1e-9

    def test_zero_ndcg_no_relevant(self):
        result = _ndcg_at_k([4, 5, 6], relevant_scores={1: 1.0, 2: 0.8}, k=3)
        assert result == 0.0

    def test_partial_ndcg_degraded_by_position(self):
        # Best item at rank 2, not rank 1 — NDCG < 1
        result = _ndcg_at_k([99, 1], relevant_scores={1: 1.0}, k=2)
        assert 0 < result < 1.0

    def test_ndcg_decreases_further_down(self):
        score_rank1 = _ndcg_at_k([1, 99], relevant_scores={1: 1.0}, k=2)
        score_rank2 = _ndcg_at_k([99, 1], relevant_scores={1: 1.0}, k=2)
        assert score_rank1 > score_rank2

    def test_empty_relevant_scores_returns_zero(self):
        result = _ndcg_at_k([1, 2, 3], relevant_scores={}, k=3)
        assert result == 0.0
