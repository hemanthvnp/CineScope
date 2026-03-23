"""
CineScope ML Service — Hybrid Recommendation Engine

Combines content-based and collaborative filtering scores to produce
the final recommendation list. Also handles cold-start scenarios.

Scoring formula:
    base_score = (CONTENT_WEIGHT × content_score) + (COLLAB_WEIGHT × collab_score)
    final_score = base_score × preference_multiplier

Preference multiplier applies boosts for:
    - Language match   : +150% if movie language matches user's preferred language
    - Era match        : +10% if movie release year falls in user's favorite era
    - Genre match      : +10% if movie genre matches user's favorite genre

Additionally, 60% of results will prioritize the user's preferred language.

Default weights: CONTENT_WEIGHT=0.4, COLLAB_WEIGHT=0.6

Cold-start handling:
- New user with no ratings → genre-based fallback using their preferences
- New user with no preferences and no ratings → trending movies
- User with few ratings (< MIN_RATINGS_FOR_COLLAB) → content-only mode
"""

import os
import re
from recommender import content_based, collaborative, explainer
from database import (
    get_all_movies, get_all_genres, get_movie_genres,
    get_user_preferences, get_user_rated_movies,
    get_all_user_ratings, get_trending_movie_ids, get_user_watchlist,
    get_user_profile
)
import tmdb_client

# Weights from environment (with defaults)
CONTENT_WEIGHT = float(os.getenv("CONTENT_WEIGHT", "0.4"))
COLLAB_WEIGHT = float(os.getenv("COLLAB_WEIGHT", "0.6"))
DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "20"))
MIN_RATINGS_FOR_COLLAB = int(os.getenv("MIN_RATINGS_FOR_COLLAB", "3"))

# Preference boost multipliers
LANG_BOOST = 1.50       # +150% for matching preferred language (strong priority)
ERA_BOOST = 0.10        # +10% for matching favorite era
GENRE_BOOST = 0.10      # +10% for matching favorite genre
LANG_PRIORITY_RATIO = 0.6  # 60% of results should be from preferred language if available

# Cache for movie data
_movies_lookup = {}
_genre_names = {}
_genre_name_to_id = {}
_movie_genre_map = {}
_models_initialized = False


def initialize_models():
    """
    Load data from MongoDB and build both ML models.
    Called once at startup and can be re-triggered to refresh.
    """
    global _movies_lookup, _genre_names, _genre_name_to_id, _movie_genre_map, _models_initialized

    print("[ml-service] Initializing recommendation models...")

    # Load reference data
    movies = get_all_movies()
    _genre_names = get_all_genres()
    _genre_name_to_id = {name.lower(): gid for gid, name in _genre_names.items()}
    _movie_genre_map = get_movie_genres()

    # Build lookup dict for quick movie access
    _movies_lookup = {m["movie_id"]: m for m in movies}

    # Build content-based model (TF-IDF)
    content_based.build_tfidf_model(movies, _movie_genre_map, _genre_names)

    # Build collaborative model (SVD)
    all_ratings = get_all_user_ratings()
    collaborative.build_svd_model(all_ratings)

    _models_initialized = True
    print(f"[ml-service] Models initialized. {len(movies)} movies, "
          f"{len(_genre_names)} genres, {len(all_ratings)} ratings")


# ---- Preference Helpers ----

def _parse_era(era_str):
    """
    Parse era string like '2010s', '1990s', '2000-2010', 'Modern' into
    a (start_year, end_year) tuple. Returns None if unparseable.
    """
    if not era_str:
        return None
    era = era_str.strip().lower()

    # Match "2010s" → 2010-2019
    m = re.match(r"(\d{4})s", era)
    if m:
        start = int(m.group(1))
        return (start, start + 9)

    # Match "2000-2010"
    m = re.match(r"(\d{4})\s*[-–]\s*(\d{4})", era)
    if m:
        return (int(m.group(1)), int(m.group(2)))

    # Match "Modern" → 2010+, "Classic" → pre-1980
    era_aliases = {
        "modern": (2010, 2030),
        "contemporary": (2000, 2030),
        "classic": (1920, 1979),
        "golden age": (1920, 1960),
        "new hollywood": (1967, 1980),
        "90s": (1990, 1999),
        "80s": (1980, 1989),
        "70s": (1970, 1979),
    }
    for alias, years in era_aliases.items():
        if alias in era:
            return years

    return None


def _get_movie_year(movie):
    """Extract release year from a movie's release_date."""
    rd = movie.get("release_date")
    if not rd:
        return None
    rd_str = str(rd)
    m = re.match(r"(\d{4})", rd_str)
    return int(m.group(1)) if m else None


def _compute_preference_boost(movie_id, user_profile):
    """
    Compute a preference multiplier for a movie based on user profile settings.

    Boosts:
      - Language match: +15% if the movie's language matches preferredLanguage
      - Era match: +10% if the movie's release year is within favoriteEra
      - Genre match: +10% if any of the movie's genres match favoriteGenre

    Returns:
        (multiplier, boost_reasons) where multiplier >= 1.0
        boost_reasons: list of strings explaining which boosts were applied
    """
    movie = _movies_lookup.get(movie_id)
    if not movie:
        return 1.0, []

    multiplier = 1.0
    boost_reasons = []

    # Language boost
    pref_lang = (user_profile.get("preferredLanguage") or "").lower().strip()
    if pref_lang:
        movie_lang = (movie.get("language") or "").lower().strip()
        if movie_lang and movie_lang == pref_lang:
            multiplier += LANG_BOOST
            boost_reasons.append(f"In your preferred language")

    # Era boost
    fav_era = user_profile.get("favoriteEra", "")
    era_range = _parse_era(fav_era)
    if era_range:
        movie_year = _get_movie_year(movie)
        if movie_year and era_range[0] <= movie_year <= era_range[1]:
            multiplier += ERA_BOOST
            boost_reasons.append(f"From your favorite era ({fav_era})")

    # Genre boost (favoriteGenre from user profile, separate from genre preference scores)
    fav_genre = user_profile.get("favoriteGenre", "").lower().strip()
    if fav_genre:
        movie_genre_ids = _movie_genre_map.get(movie_id, [])
        movie_genre_lower = [_genre_names.get(gid, "").lower() for gid in movie_genre_ids]
        if fav_genre in movie_genre_lower:
            multiplier += GENRE_BOOST
            boost_reasons.append(f"Matches your favorite genre")

    return multiplier, boost_reasons


# ---- Main Recommendation Entry Point ----

def get_hybrid_recommendations(user_id, limit=None):
    """
    Generate hybrid recommendations for a user.

    This is the main entry point. It orchestrates content-based,
    collaborative, and fallback strategies, then applies preference boosts.
    """
    if not _models_initialized:
        initialize_models()

    limit = limit or DEFAULT_LIMIT

    # Get user's data
    user_rated = get_user_rated_movies(user_id)
    user_prefs = get_user_preferences(user_id)
    user_watchlist = get_user_watchlist(user_id)
    user_profile = get_user_profile(user_id)

    # Movie IDs to exclude (already in watchlist/rated)
    exclude_ids = set()
    for entry in user_watchlist:
        exclude_ids.add(entry["movie_id"])
    for mid in user_rated:
        exclude_ids.add(mid)

    # Determine recommendation strategy
    has_ratings = len(user_rated) > 0
    has_prefs = len(user_prefs) > 0
    has_profile_prefs = bool(user_profile.get("preferredLanguage") or
                             user_profile.get("favoriteGenre") or
                             user_profile.get("favoriteEra"))
    has_enough_for_collab = len(user_rated) >= MIN_RATINGS_FOR_COLLAB

    strategy = _determine_strategy(has_ratings, has_prefs or has_profile_prefs, has_enough_for_collab)

    if strategy == "hybrid":
        recommendations = _hybrid_recommend(user_id, user_rated, user_prefs, exclude_ids, limit, user_profile)
    elif strategy == "content_only":
        recommendations = _content_only_recommend(user_rated, exclude_ids, limit, user_profile)
    elif strategy == "genre_fallback":
        recommendations = _genre_fallback_recommend(user_prefs, exclude_ids, limit, user_profile)
    else:
        recommendations = _trending_fallback_recommend(exclude_ids, limit, user_profile)

    # DYNAMICALLY MERGE ANY MISSING LANGUAGE CANDIDATES
    pref_lang = (user_profile.get("preferredLanguage") or "").lower().strip()
    if pref_lang and pref_lang != "en":
        existing_mids = {r["movie_id"] for r in recommendations}
        try:
            lang_movies = tmdb_client.fetch_discover_movies(language=pref_lang, pages=2)
            
            injected_count = 0
            for m in lang_movies:
                mid = m["movie_id"]
                if mid not in existing_mids and mid not in exclude_ids:
                    # Add to results with a base score derived from popularity
                    recommendations.append({
                        "movie_id": mid,
                        "score": round(min(m.get("popularity", 0) / 1000.0, 1.0), 4),
                        "reason_type": "language_discovery",
                        "context": {
                            "discovery_lang": pref_lang
                        }
                    })
                    injected_count += 1
                    # Populate lookup if missing
                    if mid not in _movies_lookup:
                        _movies_lookup[mid] = m
                        _movie_genre_map[mid] = m.get("genre_ids", [])
            
            if injected_count > 0:
                print(f"[ml-service] Force-injected {injected_count} {pref_lang} movies into candidate pool")
        except Exception as e:
            print(f"[ml-service] WARNING: Language discovery failed for {pref_lang}: {e}")

    # Final validation and Tier Sorting
    recommendations = _apply_preference_boosts(recommendations, user_profile, limit)

    # SECURE CHECK: Ensure recommendations is a list of dicts
    valid_recs = []
    for r in recommendations:
        if isinstance(r, dict) and "movie_id" in r:
            valid_recs.append(r)
        else:
            print(f"[ml-service] WARNING: Dropping invalid recommendation item: {r}")
    
    # Add explanations
    recommendations = explainer.explain_batch(
        valid_recs, _movies_lookup, _genre_names, _movie_genre_map
    )

    enriched = _enrich_recommendations(recommendations)

    return {
        "recommendations": enriched,
        "meta": {
            "strategy": strategy,
            "total": len(enriched),
            "limit": limit,
            "user_ratings_count": len(user_rated),
            "user_preferences_count": len(user_prefs),
            "user_profile_prefs": {
                "language": user_profile.get("preferredLanguage", ""),
                "genre": user_profile.get("favoriteGenre", ""),
                "era": user_profile.get("favoriteEra", "")
            },
            "content_model_ready": content_based.is_model_built(),
            "collab_model_ready": collaborative.is_model_built()
        }
    }


def _determine_strategy(has_ratings, has_prefs, has_enough_for_collab):
    """Determine which recommendation strategy to use."""
    if has_ratings and has_enough_for_collab and collaborative.is_model_built():
        return "hybrid"
    elif has_ratings:
        return "content_only"
    elif has_prefs:
        return "genre_fallback"
    else:
        return "trending_fallback"


def _apply_preference_boosts(results, user_profile, limit):
    """
    Apply intersection-based preference clustering to a list of results.
    Instead of multiplying scores, movies are grouped into Tiers based on 
    how many profile preferences they match:
        Tier 3: Matches Language, Era, AND Genre
        Tier 2: Matches 2 of the 3
        Tier 1: Matches 1 of the 3
        Tier 0: Matches none (baseline)
    """
    pref_lang = (user_profile.get("preferredLanguage") or "").lower().strip()
    fav_era = user_profile.get("favoriteEra", "")
    era_range = _parse_era(fav_era)
    fav_genre = (user_profile.get("favoriteGenre") or "").lower().strip()

    # If the user hasn't set any profile preferences, just sort by score and return
    if not pref_lang and not era_range and not fav_genre:
        results.sort(key=lambda x: -x["score"])
        return results[:limit]

    # Cluster results into Tiers using a weighted score
    # Lang=4, Genre=2, Era=1
    # This ensures ANY Lang match (score >= 4) beats any non-Lang match (max score 3)
    tiers = {i: [] for i in range(8)}

    for rec in results:
        movie = _movies_lookup.get(rec["movie_id"])
        if not movie:
            tiers[0].append(rec)
            continue

        weighted_score = 0
        boost_reasons = []

        # 1. Language Match (Weight 4)
        if pref_lang:
            movie_lang = (movie.get("language") or "").lower().strip()
            if movie_lang == pref_lang:
                weighted_score += 4
                boost_reasons.append("Language")

        # 2. Genre Match (Weight 2)
        if fav_genre:
            movie_genre_ids = _movie_genre_map.get(rec["movie_id"], [])
            movie_genre_lower = [_genre_names.get(gid, "").lower() for gid in movie_genre_ids]
            if fav_genre in movie_genre_lower:
                weighted_score += 2
                boost_reasons.append("Genre")

        # 3. Era Match (Weight 1)
        if era_range:
            movie_year = _get_movie_year(movie)
            if movie_year and era_range[0] <= movie_year <= era_range[1]:
                weighted_score += 1
                boost_reasons.append("Era")

        # Attach the intersection details (we still call 'matches' the count for legacy reasons or just use score)
        if boost_reasons:
            rec["context"]["intersection_tier"] = weighted_score
            rec["context"]["intersection_reasons"] = boost_reasons

        tiers[weighted_score].append(rec)

    # Build the final prioritized list: Score 7 -> 6 -> 5 -> 4 -> 3 -> 2 -> 1 -> 0
    final_results = []
    print(f"[ml-service] Final Weighted Tiers for {pref_lang}:")
    for s in range(7, -1, -1):
        if tiers[s]:
            print(f"  Score {s}: {len(tiers[s])} movies")
            # Sort internally by base algorithm score
            tiers[s].sort(key=lambda x: -x["score"])
            final_results.extend(tiers[s])

    return final_results[:limit]


def _hybrid_recommend(user_id, user_rated, user_prefs, exclude_ids, limit, user_profile):
    """Full hybrid: content + collaborative + preference boosts."""
    pool_size = limit * 10  # Deep pool to find intersection matches

    content_scores = content_based.get_content_scores(user_rated, exclude_ids, pool_size)
    collab_scores = collaborative.get_collaborative_scores(user_id, exclude_ids, pool_size)

    content_map = {}
    for mid, score, source_mid in content_scores:
        content_map[mid] = (score, source_mid)

    collab_map = {}
    for mid, score in collab_scores:
        collab_map[mid] = score

    all_candidates = set(content_map.keys()) | set(collab_map.keys())
    results = []
    similar_users = collaborative.get_similar_users_count(user_id)

    for mid in all_candidates:
        c_score = content_map.get(mid, (0, None))[0]
        c_source = content_map.get(mid, (0, None))[1]
        cb_score = collab_map.get(mid, 0)

        final_score = (CONTENT_WEIGHT * c_score) + (COLLAB_WEIGHT * cb_score)

        results.append({
            "movie_id": mid,
            "score": round(final_score, 4),
            "reason_type": "hybrid",
            "context": {
                "content_score": round(c_score, 4),
                "collab_score": round(cb_score, 4),
                "source_movie_id": c_source,
                "similar_users_count": similar_users
            }
        })

    # Sort internally before applying tiers, then pass full pool
    results.sort(key=lambda x: -x["score"])
    return _apply_preference_boosts(results[:pool_size], user_profile, limit)


def _content_only_recommend(user_rated, exclude_ids, limit, user_profile):
    """Content-based only + preference boosts."""
    pool_size = limit * 10
    content_scores = content_based.get_content_scores(user_rated, exclude_ids, pool_size)

    results = []
    for mid, score, source_mid in content_scores:
        results.append({
            "movie_id": mid,
            "score": round(score, 4),
            "reason_type": "content",
            "context": {
                "content_score": round(score, 4),
                "source_movie_id": source_mid
            }
        })

    return _apply_preference_boosts(results, user_profile, limit)


def _genre_fallback_recommend(user_prefs, exclude_ids, limit, user_profile):
    """
    Genre-based fallback + preference boosts.
    Incorporates both the genre preference scores AND profile-level preferences.
    """
    if not user_prefs and not (user_profile.get("favoriteGenre") or
                                user_profile.get("preferredLanguage") or
                                user_profile.get("favoriteEra")):
        return _trending_fallback_recommend(exclude_ids, limit, user_profile)

    scored_movies = []
    fav_genre_lower = (user_profile.get("favoriteGenre") or "").lower().strip()

    for mid, movie in _movies_lookup.items():
        if mid in exclude_ids:
            continue
        genre_ids = _movie_genre_map.get(mid, [])

        # Base score from TMDB popularity (normalized roughly to 0-3 range)
        base_popularity = min(movie.get("popularity", 0) / 1000.0, 3.0)
        
        # Score from explicit user ratings/preferences
        user_pref_score = sum(user_prefs.get(gid, 0) for gid in genre_ids)

        # Baseline score combines popularity and explicit preferences
        score = base_popularity + user_pref_score

        # Additional boost from onboarding profile favoriteGenre
        if fav_genre_lower:
            movie_genre_lower = [_genre_names.get(gid, "").lower() for gid in genre_ids]
            if fav_genre_lower in movie_genre_lower:
                score += 2.0  # Significant boost, but popularity still differentiates

        if score > 0:
            scored_movies.append((mid, score, genre_ids))

    scored_movies.sort(key=lambda x: -x[1])

    if not scored_movies:
        return _trending_fallback_recommend(exclude_ids, limit, user_profile)

    max_score = scored_movies[0][1] if scored_movies else 1
    results = []
    for mid, score, genre_ids in scored_movies:
        matching_genres = [_genre_names.get(gid, "") for gid in genre_ids if gid in (user_prefs or {})]
        results.append({
            "movie_id": mid,
            "score": round(score / max_score, 4),
            "reason_type": "genre",
            "context": {
                "genres": matching_genres
            }
        })

    # Apply preference tiers to the ENTIRE pool so we don't prune out language matches early
    return _apply_preference_boosts(results, user_profile, limit)


def _trending_fallback_recommend(exclude_ids, limit, user_profile):
    """Trending movies fallback + preference boosts."""
    trending_ids = get_trending_movie_ids(limit * 2 + len(exclude_ids))

    results = []
    for mid in trending_ids:
        if mid in exclude_ids:
            continue
        movie = _movies_lookup.get(mid)
        if movie:
            results.append({
                "movie_id": mid,
                "score": round(movie.get("popularity", 0) / 100, 4),
                "reason_type": "trending",
                "context": {}
            })

    return _apply_preference_boosts(results, user_profile, limit)


def _enrich_recommendations(recommendations):
    """Add full movie details to each recommendation."""
    enriched = []
    for rec in recommendations:
        movie = _movies_lookup.get(rec["movie_id"])
        if not movie:
            continue

        enriched.append({
            "movie_id": rec["movie_id"],
            "title": movie.get("title", "Unknown"),
            "overview": movie.get("overview", ""),
            "poster_path": movie.get("poster_path", ""),
            "vote_average": movie.get("vote_average", 0),
            "vote_count": movie.get("vote_count", 0),
            "popularity": movie.get("popularity", 0),
            "release_date": str(movie.get("release_date", "")),
            "language": movie.get("language", ""),
            "score": rec["score"],
            "explanation": rec.get("explanation", {
                "reason": "Recommended for you",
                "type": "general"
            }),
            "genres": [
                _genre_names.get(gid, "")
                for gid in _movie_genre_map.get(rec["movie_id"], [])
                if gid in _genre_names
            ],
            "context": rec.get("context", {})
        })

    return enriched
