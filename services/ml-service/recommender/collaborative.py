"""
CineScope ML Service — Collaborative Filtering Module

Implements matrix factorization using Truncated SVD (Singular Value Decomposition)
to predict how a user would rate movies they haven't seen yet.

Algorithm:
1. Build a user-item rating matrix (users as rows, movies as columns)
2. Apply Truncated SVD to decompose: R ≈ U × Σ × V^T
3. Reconstruct the full matrix to predict missing ratings
4. For the target user, extract their predicted ratings for unseen movies

Why SVD?
- Handles sparse matrices well (most users rate very few movies)
- Discovers latent factors (e.g., "likes cerebral sci-fi" or "prefers action comedies")
- Computationally efficient with truncated (low-rank) approximation

Cold Start:
- If fewer than MIN_RATINGS users/ratings exist, this module returns empty results
- The hybrid engine will fall back to content-based or genre-based recommendations
"""

import os
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD

# Module-level cache
_predicted_matrix = None
_user_index = {}     # user_id_str -> row index
_movie_index = {}    # movie_id -> column index
_index_movie = {}    # column index -> movie_id
_is_built = False

# SVD parameters
N_COMPONENTS = 20    # Number of latent factors to discover
MIN_RATINGS = 2      # Minimum total ratings needed to build the model (lowered for development)


def build_svd_model(all_ratings):
    """
    Build the SVD collaborative filtering model from all user ratings.

    Steps:
    1. Create a sparse user-item matrix from ratings
    2. Apply TruncatedSVD to find latent factors
    3. Reconstruct the full matrix with predicted ratings

    Args:
        all_ratings: list of dicts with user_id, movie_id, rating
    """
    global _predicted_matrix, _user_index, _movie_index, _index_movie, _is_built

    if len(all_ratings) < MIN_RATINGS:
        print(f"[ml-service] SVD: Not enough ratings ({len(all_ratings)}/{MIN_RATINGS}). "
              "Collaborative filtering disabled.")
        _is_built = False
        return

    # Build index mappings for users and movies
    unique_users = sorted(set(r["user_id"] for r in all_ratings))
    unique_movies = sorted(set(r["movie_id"] for r in all_ratings))

    _user_index = {uid: idx for idx, uid in enumerate(unique_users)}
    _movie_index = {mid: idx for idx, mid in enumerate(unique_movies)}
    _index_movie = {idx: mid for mid, idx in _movie_index.items()}

    n_users = len(unique_users)
    n_movies = len(unique_movies)

    # Build sparse user-item matrix
    # Each cell (i,j) = rating that user i gave to movie j
    rows, cols, data = [], [], []
    for r in all_ratings:
        uid_idx = _user_index[r["user_id"]]
        mid_idx = _movie_index[r["movie_id"]]
        rows.append(uid_idx)
        cols.append(mid_idx)
        data.append(r["rating"])

    rating_matrix = csr_matrix(
        (data, (rows, cols)),
        shape=(n_users, n_movies)
    )

    # Determine number of SVD components
    # Can't have more components than the smaller matrix dimension
    n_components = min(N_COMPONENTS, n_users - 1, n_movies - 1)
    if n_components < 1:
        print("[ml-service] SVD: Matrix too small for decomposition")
        _is_built = False
        return

    # Apply Truncated SVD
    # This decomposes R ≈ U × Σ × V^T
    # Where U captures user preferences across latent factors
    # and V captures movie characteristics across latent factors
    svd = TruncatedSVD(n_components=n_components, random_state=42)
    user_factors = svd.fit_transform(rating_matrix)  # U × Σ
    movie_factors = svd.components_                    # V^T

    # Reconstruct the full prediction matrix: R_predicted = (U × Σ) × V^T
    # This fills in the "blanks" — predicted ratings for movies users haven't seen
    _predicted_matrix = np.dot(user_factors, movie_factors)

    _is_built = True
    print(f"[ml-service] SVD model built: {n_users} users × {n_movies} movies, "
          f"{n_components} latent factors, {len(all_ratings)} ratings")


def get_collaborative_scores(user_id, exclude_ids=None, limit=50):
    """
    Get collaborative filtering scores for a user.

    For the target user, extract their row from the predicted rating matrix.
    Higher predicted values = movies the user is more likely to enjoy,
    based on patterns from similar users.

    Args:
        user_id: string user ID
        exclude_ids: set of movie_ids to exclude
        limit: max results to return

    Returns:
        list of (movie_id, normalized_score) tuples
        - score: normalized to 0-1 range
    """
    if not _is_built:
        return []

    if user_id not in _user_index:
        return []  # New user not in training data

    exclude_ids = exclude_ids or set()
    user_idx = _user_index[user_id]

    # Get this user's row of predicted ratings
    predicted_ratings = _predicted_matrix[user_idx]

    # Normalize to 0-1 range
    min_val = predicted_ratings.min()
    max_val = predicted_ratings.max()
    if max_val > min_val:
        normalized = (predicted_ratings - min_val) / (max_val - min_val)
    else:
        normalized = np.zeros_like(predicted_ratings)

    # Build results
    results = []
    for col_idx in range(len(predicted_ratings)):
        movie_id = _index_movie.get(col_idx)
        if movie_id is None:
            continue
        if movie_id in exclude_ids:
            continue

        score = float(normalized[col_idx])
        if score > 0.1:  # Minimum threshold
            results.append((movie_id, score))

    # Sort by score descending
    results.sort(key=lambda x: -x[1])
    return results[:limit]


def is_model_built():
    """Check if the SVD model has been built."""
    return _is_built


def get_similar_users_count(user_id):
    """Get the number of users in the collaborative model (for explainability)."""
    if not _is_built:
        return 0
    return len(_user_index)
