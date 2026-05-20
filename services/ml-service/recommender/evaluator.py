"""
Offline evaluation for the hybrid recommendation engine.

Uses leave-one-out evaluation: for each user with enough ratings, hold out
their highest-rated movie and check whether the content-based recommender
recovers it in the top-K results.

Metrics:
  Hit Rate@K  — fraction of users where the held-out item appears in top-K
  Precision@K — fraction of top-K results that are "relevant" (rating >= 7)
  Recall@K    — fraction of relevant items recovered in top-K
  MRR         — Mean Reciprocal Rank of the held-out item
  NDCG@K      — Normalized Discounted Cumulative Gain
  Coverage    — fraction of the movie catalog that appears in any recommendation
"""

import math
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from database import get_all_user_ratings


# ---------------------------------------------------------------------------
# Pointwise metrics
# ---------------------------------------------------------------------------

def _hit_at_k(recommended: List[int], held_out: int, k: int) -> float:
    return 1.0 if held_out in recommended[:k] else 0.0


def _precision_at_k(recommended: List[int], relevant: Set[int], k: int) -> float:
    if not recommended:
        return 0.0
    hits = sum(1 for mid in recommended[:k] if mid in relevant)
    return hits / k


def _recall_at_k(recommended: List[int], relevant: Set[int], k: int) -> float:
    if not relevant:
        return 0.0
    hits = sum(1 for mid in recommended[:k] if mid in relevant)
    return hits / len(relevant)


def _reciprocal_rank(recommended: List[int], held_out: int) -> float:
    try:
        return 1.0 / (recommended.index(held_out) + 1)
    except ValueError:
        return 0.0


def _ndcg_at_k(recommended: List[int], relevant_scores: Dict[int, float], k: int) -> float:
    dcg = sum(
        relevant_scores.get(mid, 0.0) / math.log2(i + 2)
        for i, mid in enumerate(recommended[:k])
    )
    ideal = sorted(relevant_scores.values(), reverse=True)[:k]
    idcg = sum(s / math.log2(i + 2) for i, s in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0


# ---------------------------------------------------------------------------
# Leave-one-out evaluation
# ---------------------------------------------------------------------------

def evaluate(
    k_values: List[int] = None,
    min_ratings: int = 5,
    max_users: int = 100,
) -> Dict:
    """
    Run leave-one-out evaluation on users in the database.

    Args:
        k_values:    List of K values for top-K metrics. Default [5, 10, 20].
        min_ratings: Minimum number of ratings a user must have to be included.
        max_users:   Cap on number of users evaluated (for speed).

    Returns:
        Dict with per-K metrics and catalog coverage.
    """
    from recommender import content_based
    from recommender.hybrid import _movies_lookup, _models_initialized, initialize_models

    k_values = k_values or [5, 10, 20]

    if not _models_initialized:
        initialize_models()

    if not content_based.is_model_built():
        return {"error": "Content model not ready. Call /refresh first."}

    all_ratings = get_all_user_ratings()

    user_ratings: Dict[str, Dict[int, float]] = defaultdict(dict)
    for r in all_ratings:
        user_ratings[r["user_id"]][r["movie_id"]] = r["rating"]

    eligible = [
        (uid, ratings)
        for uid, ratings in user_ratings.items()
        if len(ratings) >= min_ratings
    ][:max_users]

    if not eligible:
        return {
            "error": "Not enough users with sufficient ratings for evaluation.",
            "n_eligible": 0,
            "min_ratings_required": min_ratings,
        }

    accum: Dict[int, Dict[str, float]] = {
        k: {"hits": 0.0, "prec": 0.0, "rec": 0.0, "rr": 0.0, "ndcg": 0.0}
        for k in k_values
    }
    catalog_seen: Set[int] = set()
    n_evaluated = 0

    for user_id, movie_ratings in eligible:
        # Hold out the single highest-rated movie (must be liked, i.e. >= 7)
        liked = {mid: r for mid, r in movie_ratings.items() if r >= 7}
        if not liked:
            continue

        held_out_id = max(liked, key=liked.__getitem__)
        train_ratings = {mid: r for mid, r in movie_ratings.items() if mid != held_out_id}

        if not train_ratings:
            continue

        max_k = max(k_values)
        exclude = set(train_ratings.keys()) | {held_out_id}

        try:
            scores = content_based.get_content_scores(
                user_rated_movies=train_ratings,
                exclude_ids=exclude,
                limit=max_k + 20,
                user_profile={},
                movies_lookup=_movies_lookup,
            )
            recommended = [mid for mid, _score, _src in scores]
        except Exception:
            continue

        if not recommended:
            continue

        catalog_seen.update(recommended)
        n_evaluated += 1

        relevant = {mid for mid, r in movie_ratings.items() if r >= 7 and mid != held_out_id}
        relevant_scores = {mid: r / 10.0 for mid, r in movie_ratings.items() if r >= 7}

        for k in k_values:
            accum[k]["hits"] += _hit_at_k(recommended, held_out_id, k)
            accum[k]["prec"] += _precision_at_k(recommended, relevant, k)
            accum[k]["rec"] += _recall_at_k(recommended, relevant, k)
            accum[k]["rr"] += _reciprocal_rank(recommended, held_out_id)
            accum[k]["ndcg"] += _ndcg_at_k(recommended, relevant_scores, k)

    if n_evaluated == 0:
        return {
            "error": "No users met the held-out criteria (need at least one rating >= 7).",
            "n_eligible": len(eligible),
        }

    catalog_size = len(_movies_lookup)

    return {
        "n_evaluated": n_evaluated,
        "catalog_coverage": round(len(catalog_seen) / catalog_size, 4) if catalog_size else 0.0,
        "metrics_by_k": {
            str(k): {
                "hit_rate":  round(accum[k]["hits"] / n_evaluated, 4),
                "precision": round(accum[k]["prec"] / n_evaluated, 4),
                "recall":    round(accum[k]["rec"]  / n_evaluated, 4),
                "mrr":       round(accum[k]["rr"]   / n_evaluated, 4),
                "ndcg":      round(accum[k]["ndcg"] / n_evaluated, 4),
            }
            for k in k_values
        },
    }
