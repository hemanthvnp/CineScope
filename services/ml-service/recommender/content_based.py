"""
CineScope ML Service — Content-Based Filtering Module

Implements TF-IDF vectorization on movie overviews combined with genre tags,
then computes cosine similarity to find movies similar to what a user has liked.

Algorithm:
1. Build a combined text for each movie: overview + genre names (weighted)
2. Fit a TF-IDF vectorizer on all movie texts
3. For a given user, find their top-rated movies
4. Compute cosine similarity between those movies and all other movies
5. Rank and return the most similar movies the user hasn't seen

The TF-IDF matrix is cached in memory and rebuilt on demand.
"""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Module-level cache for the TF-IDF model
_tfidf_matrix = None
_vectorizer = None
_movie_id_index = {}  # movie_id -> row index in the matrix
_index_movie_id = {}  # row index -> movie_id
_is_built = False


def build_tfidf_model(movies, movie_genre_map, genre_names):
    """
    Build the TF-IDF model from movie data.

    For each movie, we create a combined text document:
      - The movie overview (natural language)
      - Genre names repeated 3x (to boost genre signal in TF-IDF)

    This gives us content features that capture both semantic meaning
    from descriptions AND categorical genre information.

    Args:
        movies: list of movie dicts (movie_id, title, overview)
        movie_genre_map: dict of movie_id -> [genre_ids]
        genre_names: dict of genre_id -> genre_name
    """
    global _tfidf_matrix, _vectorizer, _movie_id_index, _index_movie_id, _is_built

    documents = []
    movie_ids = []

    for movie in movies:
        mid = movie["movie_id"]
        overview = movie.get("overview", "") or ""

        # Get genre names for this movie and repeat to boost their weight
        genres = movie_genre_map.get(mid, [])
        genre_text = " ".join([
            genre_names.get(gid, "") for gid in genres
        ]) * 3  # Repeat 3x to amplify genre signal in TF-IDF

        # Combine overview and genre text into a single document
        combined = f"{overview} {genre_text}".strip()

        if combined:
            documents.append(combined)
            movie_ids.append(mid)

    if not documents:
        print("[ml-service] WARNING: No documents to build TF-IDF model")
        _is_built = False
        return

    # Build TF-IDF matrix
    # - max_features=5000: limit vocabulary size for performance
    # - stop_words='english': remove common words like 'the', 'is'
    # - ngram_range=(1,2): capture single words and bigrams like 'time travel'
    _vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=2,       # Ignore terms appearing in fewer than 2 documents
        max_df=0.85     # Ignore terms appearing in more than 85% of documents
    )
    _tfidf_matrix = _vectorizer.fit_transform(documents)

    # Build index mappings
    _movie_id_index = {mid: idx for idx, mid in enumerate(movie_ids)}
    _index_movie_id = {idx: mid for idx, mid in enumerate(movie_ids)}

    _is_built = True
    print(f"[ml-service] TF-IDF model built: {len(documents)} movies, "
          f"{_tfidf_matrix.shape[1]} features")


def get_content_scores(user_rated_movies, exclude_ids=None, limit=50):
    """
    Compute content-based recommendation scores for a user.

    Strategy:
    1. Take the user's top-rated movies (score >= 6)
    2. For each, compute cosine similarity against all other movies
    3. Average the similarities across all seed movies
    4. This gives a "content affinity" score for every movie

    Args:
        user_rated_movies: dict of movie_id -> rating (1-10)
        exclude_ids: set of movie_ids to exclude from results
        limit: max number of results

    Returns:
        list of (movie_id, score, best_match_movie_id) tuples
        - score: normalized 0-1 content similarity score
        - best_match_movie_id: the rated movie this is most similar to
    """
    if not _is_built or not user_rated_movies:
        return []

    exclude_ids = exclude_ids or set()

    # Select seeds: separate into positive (rating >= 5) and negative (rating < 5)
    pos_seeds = []
    neg_seeds = []
    
    # Sort all rated movies by rating (descending)
    sorted_ratings = sorted(user_rated_movies.items(), key=lambda x: -x[1])
    
    for mid, rating in sorted_ratings:
        if mid not in _movie_id_index:
            continue
            
        if rating >= 6:  # Strong positive signal
            if len(pos_seeds) < 10:
                pos_seeds.append((mid, rating))
        elif rating <= 3:  # Strong negative signal
            if len(neg_seeds) < 10:
                neg_seeds.append((mid, rating))
        # Ratings 4-5 are neutral and ignored for seeding

    if not pos_seeds and not neg_seeds:
        return []

    n_movies = _tfidf_matrix.shape[0]
    pos_scores = np.zeros(n_movies)
    neg_scores = np.zeros(n_movies)
    best_match = {}  # movie_id -> (seed_movie_id, similarity)

    # 1. Compute Positive Affinity
    total_pos_weight = 0
    for seed_mid, rating in pos_seeds:
        seed_idx = _movie_id_index[seed_mid]
        sim_scores = cosine_similarity(_tfidf_matrix[seed_idx:seed_idx + 1], _tfidf_matrix).flatten()
        
        weight = rating / 10.0
        pos_scores += sim_scores * weight
        total_pos_weight += weight

        # Track best matches for explanations
        for idx in range(n_movies):
            mid = _index_movie_id[idx]
            if mid not in best_match or sim_scores[idx] > best_match[mid][1]:
                best_match[mid] = (seed_mid, sim_scores[idx])

    if total_pos_weight > 0:
        pos_scores /= total_pos_weight

    # 2. Compute Negative Affinity (Penalty)
    total_neg_weight = 0
    for seed_mid, rating in neg_seeds:
        seed_idx = _movie_id_index[seed_mid]
        sim_scores = cosine_similarity(_tfidf_matrix[seed_idx:seed_idx + 1], _tfidf_matrix).flatten()
        
        # Invert weight: 1/10 rating means HIGHER penalty
        weight = (10 - rating) / 10.0
        neg_scores += sim_scores * weight
        total_neg_weight += weight

    if total_neg_weight > 0:
        neg_scores /= total_neg_weight

    # 3. Combine: Affinity - Penalty
    # We use a penalty multiplier to make dislikes strong
    PENALTY_MULTIPLIER = 1.25
    final_scores = pos_scores - (PENALTY_MULTIPLIER * neg_scores)

    # Build results: (movie_id, score, best_match_movie_id)
    results = []
    for idx in range(n_movies):
        movie_id = _index_movie_id[idx]
        if movie_id in exclude_ids or movie_id in user_rated_movies:
            continue

        score = float(final_scores[idx])
        # If no positive matches, but strong negative matches, score will be negative.
        # We cap it at 0.0 for the final results to keep them as "recommendations",
        # but the sorting will naturally push penalized items to the very bottom.
        if score > 0.01:
            match_mid = best_match.get(movie_id, (None, 0))[0]
            results.append((movie_id, score, match_mid))

    # Sort and limit
    results.sort(key=lambda x: -x[1])
    return results[:limit]


def is_model_built():
    """Check if the TF-IDF model has been built."""
    return _is_built
