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

# Hybrid weights
CONTENT_WEIGHT = 0.75   # Increased from 0.7 for stronger historical matching
COLLAB_WEIGHT = 0.25    # Decreased from 0.3 for less general community influence
DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "20"))
MIN_RATINGS_FOR_COLLAB = int(os.getenv("MIN_RATINGS_FOR_COLLAB", "3"))
MIN_ACCEPTABLE_VOTE_AVG = float(os.getenv("MIN_ACCEPTABLE_VOTE_AVG", "6.0"))
MIN_ACCEPTABLE_VOTE_COUNT = int(os.getenv("MIN_ACCEPTABLE_VOTE_COUNT", "80"))

# Preference boost multipliers
LANG_BOOST = 2.0        # +200% for matching preferred language (strong priority)
ERA_BOOST = 0.25        # +25% for matching favorite era
GENRE_BOOST = 0.25      # +25% for matching favorite genre
LANG_PRIORITY_RATIO = 0.7  # 70% of results should be from preferred language if available

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

    # Build lookup and genre maps directly from fetched movies
    _movies_lookup = {}
    _movie_genre_map = {}
    for m in movies:
        mid = m["movie_id"]
        _movies_lookup[mid] = m
        _movie_genre_map[mid] = m.get("genre_ids", [])

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


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _compute_quality_score(movie):
    """
    Compute a quality score in [0,1] from vote average, confidence, popularity.
    """
    if not movie:
        return 0.0

    vote_avg = _safe_float(movie.get("vote_average"), 0.0)
    vote_count = _safe_float(movie.get("vote_count"), 0.0)
    popularity = _safe_float(movie.get("popularity"), 0.0)

    rating_norm = max(0.0, min(vote_avg / 10.0, 1.0))
    confidence = min(vote_count / 500.0, 1.0)
    popularity_norm = min(popularity / 200.0, 1.0)

    return round((0.60 * rating_norm) + (0.25 * confidence) + (0.15 * popularity_norm), 4)


def _passes_quality_floor(movie, is_regional=False):
    """
    Filter out weak titles when enough stronger options exist.
    Regional languages (non-English) have lower vote count thresholds.
    """
    if not movie:
        return False
    
    vote_avg = _safe_float(movie.get("vote_average"), 0.0)
    vote_count = _safe_float(movie.get("vote_count"), 0.0)
    
    # Relaxed floor for regional cinema or high-rated gems
    min_votes = MIN_ACCEPTABLE_VOTE_COUNT if not is_regional else max(30, MIN_ACCEPTABLE_VOTE_COUNT // 3)
    min_avg = MIN_ACCEPTABLE_VOTE_AVG if not is_regional else 6.0
    
    return vote_avg >= min_avg and vote_count >= min_votes


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
        recommendations = _hybrid_recommend(user_id, user_rated, user_prefs, exclude_ids, limit * 2, user_profile)
    elif strategy == "content_only":
        recommendations = _content_only_recommend(user_rated, exclude_ids, limit * 2, user_profile)
    elif strategy == "genre_fallback":
        recommendations = _genre_fallback_recommend(user_prefs, exclude_ids, limit * 2, user_profile)
    else:
        recommendations = _trending_fallback_recommend(exclude_ids, limit * 2, user_profile)

    # DYNAMICALLY MERGE ANY MISSING LANGUAGE CANDIDATES
    pref_lang = (user_profile.get("preferredLanguage") or "").lower().strip()
    if pref_lang and pref_lang != "en":
        existing_mids = {r["movie_id"] for r in recommendations}
        try:
            lang_movies = tmdb_client.fetch_discover_movies(language=pref_lang, pages=8) # More pages
            
            injected_count = 0
            for m in lang_movies:
                mid = m["movie_id"]
                if mid not in existing_mids and mid not in exclude_ids:
                    is_m_regional = (m.get("language") or m.get("original_language") or "").lower() != "en"
                    # For language injection, we use a VERY relaxed floor to ensure we get results
                    if not _passes_quality_floor(m, is_regional=True):
                        continue
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

    # Final validation and Tier Sorting (this is the ONLY place we should truncate to limit)
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
        def _no_pref_sort_key(rec):
            movie = _movies_lookup.get(rec["movie_id"], {})
            quality = _compute_quality_score(movie)
            base = rec.get("score", 0.0)
            return ((0.7 * base) + (0.3 * quality), base, quality)

        results.sort(key=_no_pref_sort_key, reverse=True)
        
        def _is_rec_high_quality(r):
            movie = _movies_lookup.get(r["movie_id"], {})
            is_reg = (movie.get("language") or movie.get("original_language") or "").lower() != "en"
            return _passes_quality_floor(movie, is_regional=is_reg)

        high_quality = [r for r in results if _is_rec_high_quality(r)]
        if len(high_quality) >= limit:
            return high_quality[:limit]
        return (high_quality + [r for r in results if r not in high_quality])[:limit]

    # Group results by how many active preferences they satisfy.
    # This enforces intersection-first ranking:
    #   1) movies matching ALL active preferences first
    #   2) then movies matching (N-1), then (N-2), ...
    active_pref_count = int(bool(pref_lang)) + int(bool(era_range)) + int(bool(fav_genre))
    tiers = {i: [] for i in range(active_pref_count + 1)}

    for rec in results:
        movie = _movies_lookup.get(rec["movie_id"])
        if not movie:
            tiers[0].append(rec)
            continue

        match_count = 0
        boost_reasons = []

        # 1. Language match
        if pref_lang:
            movie_lang = (movie.get("language") or movie.get("original_language") or "").lower().strip()
            if movie_lang == pref_lang:
                match_count += 1
                boost_reasons.append("Language")

        # 2. Genre match
        if fav_genre:
            movie_genre_ids = _movie_genre_map.get(rec["movie_id"], [])
            movie_genre_lower = [_genre_names.get(gid, "").lower() for gid in movie_genre_ids]
            if fav_genre in movie_genre_lower:
                match_count += 1
                boost_reasons.append("Genre")

        # 3. Era match
        if era_range:
            movie_year = _get_movie_year(movie)
            if movie_year and era_range[0] <= movie_year <= era_range[1]:
                match_count += 1
                boost_reasons.append("Era")

        # Attach intersection details for explainability/debugging.
        rec_context = rec.get("context")
        if not isinstance(rec_context, dict):
            rec_context = {}
            rec["context"] = rec_context
        
        is_movie_regional = (movie.get("language") or movie.get("original_language") or "").lower() != "en"
        rec_context["matched_preferences"] = match_count
        rec_context["active_preferences"] = active_pref_count
        rec_context["is_full_intersection"] = (active_pref_count > 0 and match_count == active_pref_count)
        rec_context["quality_score"] = _compute_quality_score(movie)
        rec_context["passes_quality_floor"] = _passes_quality_floor(movie, is_regional=is_movie_regional)

        if boost_reasons:
            rec_context["intersection_tier"] = match_count
            rec_context["intersection_reasons"] = boost_reasons

        tiers[match_count].append(rec)

    # Build final list by intersection strength: N -> ... -> 0
    final_results = []
    print(f"[ml-service] Final Intersection Tiers for {pref_lang}:")
    for s in range(active_pref_count, -1, -1):
        if tiers[s]:
            print(f"  Match Count {s}/{active_pref_count}: {len(tiers[s])} movies")
            # Sort internally by blended relevance + quality score.
            def _tier_sort_key(rec):
                movie = _movies_lookup.get(rec["movie_id"], {})
                quality = rec.get("context", {}).get("quality_score", _compute_quality_score(movie))
                base = rec.get("score", 0.0)
                blended = (0.65 * base) + (0.35 * quality)
                return (blended, base, quality, _safe_float(movie.get("popularity"), 0.0))

            tiers[s].sort(key=_tier_sort_key, reverse=True)
            final_results.extend(tiers[s])

    high_quality = [r for r in final_results if r.get("context", {}).get("passes_quality_floor")]
    if len(high_quality) >= limit:
        return high_quality[:limit]

    # If we don't have enough high-quality results, fill with lower-quality but still relevant ones
    results_so_far = high_quality
    needed = limit - len(results_so_far)
    
    if needed > 0:
        low_quality = [r for r in final_results if not r.get("context", {}).get("passes_quality_floor")]
        results_so_far.extend(low_quality[:needed])
        
    # FINAL SAFETY: If still less than limit, fill with trending movies in preferred language
    if len(results_so_far) < limit:
        needed = limit - len(results_so_far)
        exclude_ids.update({r["movie_id"] for r in results_so_far})
        
        try:
            trending_regional = tmdb_client.fetch_discover_movies(language=pref_lang or "ta", pages=2)
            for m in trending_regional:
                if m["movie_id"] not in exclude_ids and len(results_so_far) < limit:
                    results_so_far.append({
                        "movie_id": m["movie_id"],
                        "score": 0.1,
                        "reason_type": "trending_discovery",
                        "context": {"discovery_lang": pref_lang or "ta"}
                    })
                    # Populate lookup if missing
                    if m["movie_id"] not in _movies_lookup:
                        _movies_lookup[m["movie_id"]] = m
                        _movie_genre_map[m["movie_id"]] = m.get("genre_ids", [])
        except:
            pass

    return results_so_far[:limit]


def _hybrid_recommend(user_id, user_rated, user_prefs, exclude_ids, limit, user_profile):
    """Full hybrid: content + collaborative + preference boosts."""
    pool_size = limit * 20  # Even deeper pool to find high-intersection matches in larger dataset

    content_scores = content_based.get_content_scores(
        user_rated, exclude_ids, pool_size, user_profile, _movies_lookup
    )
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
    
    # DEBUG LOG: Check how many candidates we have per language
    if results:
        langs = {}
        for r in results:
            m = _movies_lookup.get(r["movie_id"], {})
            l = m.get("original_language", "??")
            langs[l] = langs.get(l, 0) + 1
        print(f"[ml-service] Candidate Pool Breakdown by Language: {langs}")
        
    return results[:pool_size]


def _content_only_recommend(user_rated, exclude_ids, limit, user_profile):
    """Content-based only + preference boosts."""
    pool_size = limit * 10
    content_scores = content_based.get_content_scores(
        user_rated, exclude_ids, pool_size, user_profile, _movies_lookup
    )

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

    return results[:limit]


def _genre_fallback_recommend(user_prefs, exclude_ids, limit, user_profile):
    """
    Enhanced genre-based fallback that intersects ALL user preferences.
    Combines explicit genre ratings with profile preferences (genre, language, era).
    """
    if not user_prefs and not (user_profile.get("favoriteGenre") or
                                user_profile.get("preferredLanguage") or
                                user_profile.get("favoriteEra")):
        return _trending_fallback_recommend(exclude_ids, limit, user_profile)

    scored_movies = []
    fav_genre_lower = (user_profile.get("favoriteGenre") or "").lower().strip()
    pref_lang = (user_profile.get("preferredLanguage") or "").lower().strip()
    pref_era = (user_profile.get("favoriteEra") or "").lower().strip()

    for mid, movie in _movies_lookup.items():
        if mid in exclude_ids:
            continue
        genre_ids = _movie_genre_map.get(mid, [])
        
        # Calculate score based on how strongly the movie aligns
        # with explicit genre preferences + profile preferences.
        score_factors = []
        matching_preferences = []

        # 1. Explicit genre preference scores
        user_pref_score = sum(user_prefs.get(gid, 0) for gid in genre_ids)
        if user_pref_score > 0:
            score_factors.append(user_pref_score)
            matching_genres = [_genre_names.get(gid, "") for gid in genre_ids if gid in (user_prefs or {})]
            matching_preferences.extend(matching_genres)

        # 2. Profile favorite genre match
        if fav_genre_lower:
            movie_genre_lower = [_genre_names.get(gid, "").lower() for gid in genre_ids]
            if fav_genre_lower in movie_genre_lower:
                score_factors.append(2.0)
                matching_preferences.append(fav_genre_lower.title())

        # 3. Language preference match
        if pref_lang and pref_lang != "en":
            movie_lang = (movie.get("original_language") or "").lower()
            if movie_lang == pref_lang:
                score_factors.append(1.5)
                matching_preferences.append(f"{pref_lang.upper()} language")

        # 4. Era preference match
        if pref_era:
            release_year = str(movie.get("release_date", "")).split("-")[0]
            if release_year and _is_era_match(release_year, pref_era):
                score_factors.append(1.0)
                matching_preferences.append(pref_era)

        # Base popularity score (normalized)
        base_popularity = min(movie.get("popularity", 0) / 1000.0, 3.0)
        if base_popularity > 0:
            score_factors.append(base_popularity)

        # Final score is sum of all matching factors
        final_score = sum(score_factors)

        if final_score > 0:
            scored_movies.append((mid, final_score, genre_ids, matching_preferences, movie))

    scored_movies.sort(key=lambda x: -x[1])

    if not scored_movies:
        return _trending_fallback_recommend(exclude_ids, limit, user_profile)

    max_score = scored_movies[0][1] if scored_movies else 1
    results = []
    for mid, score, genre_ids, matching_prefs, movie in scored_movies[:limit * 3]:  # Get more candidates
        # Get genre names for explanation
        genre_names = [_genre_names.get(gid, "") for gid in genre_ids if gid in _genre_names]
        
        results.append({
            "movie_id": mid,
            "score": round(score / max_score, 4),
            "reason_type": "genre_intersection",
            "context": {
                "matching_genres": genre_names[:3],  # Top 3 genres
                "matching_preferences": sorted(set(matching_prefs)),  # Unique preferences
                "genre_count": len([g for g in genre_ids if g in (user_prefs or {})]),
                "language_match": bool(pref_lang and movie.get("original_language", "").lower() == pref_lang),
                "era_match": bool(pref_era and _is_era_match(str(movie.get("release_date", "")).split("-")[0], pref_era))
            }
        })

    return results


def _is_era_match(release_year, era_preference):
    """Check if a movie's release year matches the user's era preference."""
    if not release_year or not era_preference:
        return False
    
    try:
        year = int(release_year)
        era = era_preference.lower()
        
        if era == "classic":
            return year < 1970
        elif era == "modern":
            return year >= 2010
        elif era.endswith("s"):
            era_start = int(era[:4])
            era_end = era_start + 9
            return era_start <= year <= era_end
        elif "-" in era:
            start, end = map(int, era.split("-"))
            return start <= year <= end
    except (ValueError, AttributeError):
        return False
    
    return False


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

    return results


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
