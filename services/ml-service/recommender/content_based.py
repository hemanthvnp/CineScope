

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_tfidf_matrix = None
_vectorizer = None
_movie_id_index = {}
_index_movie_id = {}
_is_built = False


def build_tfidf_model(movies, movie_genre_map, genre_names):
    global _tfidf_matrix, _vectorizer, _movie_id_index, _index_movie_id, _is_built

    documents = []
    movie_ids = []

    for movie in movies:
        mid = movie["movie_id"]
        overview = movie.get("overview", "") or ""
        title = movie.get("title", "") or ""

        genres = movie_genre_map.get(mid, [])
        genre_text = " ".join([
            genre_names.get(gid, "") for gid in genres
        ]) * 4

        combined = f"{title} {overview} {genre_text}".strip()

        if combined:
            documents.append(combined)
            movie_ids.append(mid)

    if not documents:
        print("[ml-service] WARNING: No documents to build TF-IDF model")
        _is_built = False
        return

    _vectorizer = TfidfVectorizer(
        max_features=10000,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.9
    )
    _tfidf_matrix = _vectorizer.fit_transform(documents)

    _movie_id_index = {mid: idx for idx, mid in enumerate(movie_ids)}
    _index_movie_id = {idx: mid for idx, mid in enumerate(movie_ids)}

    _is_built = True
    print(f"[ml-service] TF-IDF model built: {len(documents)} movies, "
          f"{_tfidf_matrix.shape[1]} features")


def get_content_scores(user_rated_movies, exclude_ids=None, limit=50, user_profile=None, movies_lookup=None):
    if not _is_built or not user_rated_movies:
        return []

    exclude_ids = exclude_ids or set()
    pref_lang = (user_profile.get("preferredLanguage") or "").lower().strip() if user_profile else None

    pos_seeds = []
    neg_seeds = []
    
    def _seed_sort_key(item):
        mid, rating = item
        lang_match = False
        if pref_lang and movies_lookup and mid in movies_lookup:
            movie = movies_lookup[mid]
            movie_lang = (movie.get("language") or movie.get("original_language") or "").lower().strip()
            lang_match = (movie_lang == pref_lang)
        
        return (rating, 1 if lang_match else 0)

    sorted_ratings = sorted(user_rated_movies.items(), key=_seed_sort_key, reverse=True)
    
    for mid, rating in sorted_ratings:
        if mid not in _movie_id_index:
            continue
            
        if rating >= 6:
            if len(pos_seeds) < 10:
                pos_seeds.append((mid, rating))
        elif rating <= 3:
            if len(neg_seeds) < 10:
                neg_seeds.append((mid, rating))

    if not pos_seeds and not neg_seeds:
        return []

    n_movies = _tfidf_matrix.shape[0]
    pos_scores = np.zeros(n_movies)
    neg_scores = np.zeros(n_movies)
    best_match = {}

    total_pos_weight = 0
    seed_candidates = {}
    
    for seed_mid, rating in pos_seeds:
        seed_idx = _movie_id_index[seed_mid]
        sim_scores = cosine_similarity(_tfidf_matrix[seed_idx:seed_idx + 1], _tfidf_matrix).flatten()
        
        weight = rating / 10.0
        pos_scores += sim_scores * weight
        total_pos_weight += weight

        top_indices = np.argsort(sim_scores)[::-1][:limit*2]
        seed_candidates[seed_mid] = []
        for idx in top_indices:
            mid = _index_movie_id[idx]
            if mid not in exclude_ids and mid not in user_rated_movies:
                seed_candidates[seed_mid].append((mid, sim_scores[idx]))
                if mid not in best_match or sim_scores[idx] > best_match[mid][1]:
                    best_match[mid] = (seed_mid, sim_scores[idx])

    if total_pos_weight > 0:
        pos_scores /= total_pos_weight

    total_neg_weight = 0
    for seed_mid, rating in neg_seeds:
        seed_idx = _movie_id_index[seed_mid]
        sim_scores = cosine_similarity(_tfidf_matrix[seed_idx:seed_idx + 1], _tfidf_matrix).flatten()
        
        weight = (10 - rating) / 10.0
        neg_scores += sim_scores * weight
        total_neg_weight += weight

    if total_neg_weight > 0:
        neg_scores /= total_neg_weight

    PENALTY_MULTIPLIER = 1.5
    
    final_results_dict = {}
    
    per_seed_limit = max(8, limit // len(pos_seeds)) if pos_seeds else 0
    
    for seed_mid, candidates in seed_candidates.items():
        seed_movie = movies_lookup.get(seed_mid, {})
        seed_lang = (seed_movie.get("language") or seed_movie.get("original_language") or "").lower().strip()
        
        for mid, sim in candidates[:per_seed_limit * 2]:
            mid_idx = _movie_id_index[mid]
            penalty = neg_scores[mid_idx] * PENALTY_MULTIPLIER
            
            blended_score = (0.3 * pos_scores[mid_idx]) + (0.7 * sim) - penalty
            
            candidate_movie = movies_lookup.get(mid, {})
            cand_lang = (candidate_movie.get("language") or candidate_movie.get("original_language") or "").lower().strip()
            if cand_lang == seed_lang and cand_lang != "en":
                blended_score *= 1.2
            
            if blended_score > 0.03:
                if mid not in final_results_dict or blended_score > final_results_dict[mid][0]:
                    final_results_dict[mid] = (blended_score, seed_mid)

    results = []
    for mid, (score, match_mid) in final_results_dict.items():
        results.append((mid, score, match_mid))

    results.sort(key=lambda x: -x[1])
    return results[:limit]


def is_model_built():
    return _is_built
