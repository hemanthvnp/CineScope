

import os
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD

_predicted_matrix = None
_user_index = {}
_movie_index = {}
_index_movie = {}
_is_built = False
N_COMPONENTS = 20
MIN_RATINGS = 2


def build_svd_model(all_ratings):
    global _predicted_matrix, _user_index, _movie_index, _index_movie, _is_built

    if len(all_ratings) < MIN_RATINGS:
        print(f"[ml-service] SVD: Not enough ratings ({len(all_ratings)}/{MIN_RATINGS}). "
              "Collaborative filtering disabled.")
        _is_built = False
        return

    unique_users = sorted(set(r["user_id"] for r in all_ratings))
    unique_movies = sorted(set(r["movie_id"] for r in all_ratings))

    _user_index = {uid: idx for idx, uid in enumerate(unique_users)}
    _movie_index = {mid: idx for idx, mid in enumerate(unique_movies)}
    _index_movie = {idx: mid for mid, idx in _movie_index.items()}

    n_users = len(unique_users)
    n_movies = len(unique_movies)

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

    n_components = min(N_COMPONENTS, n_users - 1, n_movies - 1)
    if n_components < 1:
        print("[ml-service] SVD: Matrix too small for decomposition")
        _is_built = False
        return

    svd = TruncatedSVD(n_components=n_components, random_state=42)
    user_factors = svd.fit_transform(rating_matrix)
    movie_factors = svd.components_

    _predicted_matrix = np.dot(user_factors, movie_factors)

    _is_built = True
    print(f"[ml-service] SVD model built: {n_users} users × {n_movies} movies, "
          f"{n_components} latent factors, {len(all_ratings)} ratings")


def get_collaborative_scores(user_id, exclude_ids=None, limit=50):
    if not _is_built:
        return []

    if user_id not in _user_index:
        return []

    exclude_ids = exclude_ids or set()
    user_idx = _user_index[user_id]

    predicted_ratings = _predicted_matrix[user_idx]

    min_val = predicted_ratings.min()
    max_val = predicted_ratings.max()
    if max_val > min_val:
        normalized = (predicted_ratings - min_val) / (max_val - min_val)
    else:
        normalized = np.zeros_like(predicted_ratings)

    results = []
    for col_idx in range(len(predicted_ratings)):
        movie_id = _index_movie.get(col_idx)
        if movie_id is None:
            continue
        if movie_id in exclude_ids:
            continue

        score = float(normalized[col_idx])
        if score > 0.1:
            results.append((movie_id, score))

    results.sort(key=lambda x: -x[1])
    return results[:limit]


def is_model_built():
    return _is_built


def get_similar_users_count(user_id):
    if not _is_built:
        return 0
    return len(_user_index)
