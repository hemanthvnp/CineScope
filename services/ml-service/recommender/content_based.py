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
        title = movie.get("title", "") or ""

        # Get genre names for this movie and repeat to boost their weight
        genres = movie_genre_map.get(mid, [])
        genre_text = " ".join([
            genre_names.get(gid, "") for gid in genres
        ]) * 4  # Repeat 4x to amplify genre signal in TF-IDF

        # Combine title, overview and genre text into a single document
        # Title is added to help catch direct title matches in similarity
        combined = f"{title} {overview} {genre_text}".strip()

        if combined:
            documents.append(combined)
            movie_ids.append(mid)

    if not documents:
        print("[ml-service] WARNING: No documents to build TF-IDF model")
        _is_built = False
        return

    # Build TF-IDF matrix
    # - max_features=10000: larger vocabulary for more precision
    # - stop_words='english': remove common words like 'the', 'is'
    # - ngram_range=(1,2): capture single words and bigrams like 'time travel'
    _vectorizer = TfidfVectorizer(
        max_features=10000,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=1,       # Include terms appearing in even 1 document
        max_df=0.9      # Ignore terms appearing in more than 90% of documents
    )
    _tfidf_matrix = _vectorizer.fit_transform(documents)

    # Build index mappings
    _movie_id_index = {mid: idx for idx, mid in enumerate(movie_ids)}
    _index_movie_id = {idx: mid for idx, mid in enumerate(movie_ids)}

    _is_built = True
    print(f"[ml-service] TF-IDF model built: {len(documents)} movies, "
          f"{_tfidf_matrix.shape[1]} features")


def get_content_scores(user_rated_movies, exclude_ids=None, limit=50, user_profile=None, movies_lookup=None):
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
        user_profile: dict with user preferences (language, genre, era)
        movies_lookup: dict of movie_id -> movie_details

    Returns:
        list of (movie_id, score, best_match_movie_id) tuples
        - score: normalized 0-1 content similarity score
        - best_match_movie_id: the rated movie this is most similar to
    """
    if not _is_built or not user_rated_movies:
        return []

    exclude_ids = exclude_ids or set()
    pref_lang = (user_profile.get("preferredLanguage") or "").lower().strip() if user_profile else None

    # Select seeds: separate into positive (rating >= 5) and negative (rating < 5)
    pos_seeds = []
    neg_seeds = []
    
    # Sort all rated movies by rating (descending)
    # SECONDARY SORT: Prioritize movies that match the user's preferred language
    def _seed_sort_key(item):
        mid, rating = item
        lang_match = False
        if pref_lang and movies_lookup and mid in movies_lookup:
            movie = movies_lookup[mid]
            movie_lang = (movie.get("language") or movie.get("original_language") or "").lower().strip()
            lang_match = (movie_lang == pref_lang)
        
        # Priority: 1. Rating, 2. Language Match
        return (rating, 1 if lang_match else 0)

    sorted_ratings = sorted(user_rated_movies.items(), key=_seed_sort_key, reverse=True)
    
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
    # Collect candidates per seed to ensure variety
    seed_candidates = {} # seed_mid -> list of (movie_id, similarity)
    
    for seed_mid, rating in pos_seeds:
        seed_idx = _movie_id_index[seed_mid]
        sim_scores = cosine_similarity(_tfidf_matrix[seed_idx:seed_idx + 1], _tfidf_matrix).flatten()
        
        weight = rating / 10.0
        pos_scores += sim_scores * weight
        total_pos_weight += weight

        # Collect top candidates for this specific seed
        top_indices = np.argsort(sim_scores)[::-1][:limit*2]
        seed_candidates[seed_mid] = []
        for idx in top_indices:
            mid = _index_movie_id[idx]
            if mid not in exclude_ids and mid not in user_rated_movies:
                seed_candidates[seed_mid].append((mid, sim_scores[idx]))
                # Track best match for initial explanation
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

    # 3. Combine and Fair Selection
    # We want to ensure every seed contributes some top matches
    # to avoid one seed (like a Hollywood hit) dominating the row.
    
    PENALTY_MULTIPLIER = 1.5
    
    # Final candidates set
    final_results_dict = {} # mid -> (score, best_match_mid)
    
    # Take top N from EACH seed to ensure variety
    per_seed_limit = max(8, limit // len(pos_seeds)) if pos_seeds else 0
    
    for seed_mid, candidates in seed_candidates.items():
        # Get seed details for language matching
        seed_movie = movies_lookup.get(seed_mid, {})
        seed_lang = (seed_movie.get("language") or seed_movie.get("original_language") or "").lower().strip()
        
        for mid, sim in candidates[:per_seed_limit * 2]: # Look at more candidates per seed
            # Compute final penalized score for this candidate
            mid_idx = _movie_id_index[mid]
            penalty = neg_scores[mid_idx] * PENALTY_MULTIPLIER
            
            # Weighted affinity from all seeds + specific boost for this seed's similarity
            # This makes a movie that is a perfect match for ONE seed rank highly
            # even if it's not a match for others.
            blended_score = (0.3 * pos_scores[mid_idx]) + (0.7 * sim) - penalty
            
            # EXTRA BOOST: If the candidate matches the seed's language, give it a bump
            # This helps preserve regional clusters
            candidate_movie = movies_lookup.get(mid, {})
            cand_lang = (candidate_movie.get("language") or candidate_movie.get("original_language") or "").lower().strip()
            if cand_lang == seed_lang and cand_lang != "en":
                blended_score *= 1.2
            
            if blended_score > 0.03:
                if mid not in final_results_dict or blended_score > final_results_dict[mid][0]:
                    final_results_dict[mid] = (blended_score, seed_mid)

    # Convert to list and sort
    results = []
    for mid, (score, match_mid) in final_results_dict.items():
        results.append((mid, score, match_mid))

    results.sort(key=lambda x: -x[1])
    return results[:limit]


def is_model_built():
    """Check if the TF-IDF model has been built."""
    return _is_built
