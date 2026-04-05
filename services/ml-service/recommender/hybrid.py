

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

CONTENT_WEIGHT = 0.75
COLLAB_WEIGHT = 0.25
DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "20"))
MIN_RATINGS_FOR_COLLAB = int(os.getenv("MIN_RATINGS_FOR_COLLAB", "3"))
MIN_ACCEPTABLE_VOTE_AVG = float(os.getenv("MIN_ACCEPTABLE_VOTE_AVG", "6.0"))
MIN_ACCEPTABLE_VOTE_COUNT = int(os.getenv("MIN_ACCEPTABLE_VOTE_COUNT", "80"))

LANG_BOOST = 2.0
ERA_BOOST = 0.25
GENRE_BOOST = 0.25
LANG_PRIORITY_RATIO = 0.7
_movies_lookup = {}
_genre_names = {}
_genre_name_to_id = {}
_movie_genre_map = {}
_models_initialized = False


def initialize_models():
    global _movies_lookup, _genre_names, _genre_name_to_id, _movie_genre_map, _models_initialized

    print("[ml-service] Initializing recommendation models...")

    movies = get_all_movies()
    _genre_names = get_all_genres()
    _genre_name_to_id = {name.lower(): gid for gid, name in _genre_names.items()}

    _movies_lookup = {}
    _movie_genre_map = {}
    for m in movies:
        mid = m["movie_id"]
        _movies_lookup[mid] = m
        _movie_genre_map[mid] = m.get("genre_ids", [])

    content_based.build_tfidf_model(movies, _movie_genre_map, _genre_names)

    _models_initialized = True
    print(f"[ml-service] Models initialized. {len(movies)} movies, "
          f"{len(_genre_names)} genres, {len(all_ratings)} ratings")




def _parse_era(era_str):
    if not era_str:
        return None
    era = era_str.strip().lower()

    m = re.match(r"(\d{4})s", era)
    if m:
        start = int(m.group(1))
        return (start, start + 9)

    # Match "2000-2010"
    m = re.match(r"(\d{4})\s*[-–]\s*(\d{4})", era)
    if m:
        return (int(m.group(1)), int(m.group(2)))

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
    if not movie:
        return False
    
    vote_avg = _safe_float(movie.get("vote_average"), 0.0)
    vote_count = _safe_float(movie.get("vote_count"), 0.0)
    
    min_votes = MIN_ACCEPTABLE_VOTE_COUNT if not is_regional else max(30, MIN_ACCEPTABLE_VOTE_COUNT // 3)
    min_avg = MIN_ACCEPTABLE_VOTE_AVG if not is_regional else 6.0
    
    return vote_avg >= min_avg and vote_count >= min_votes


def _compute_preference_boost(movie_id, user_profile):
    movie = _movies_lookup.get(movie_id)
    if not movie:
        return 1.0, []

    multiplier = 1.0
    boost_reasons = []

    pref_lang = (user_profile.get("preferredLanguage") or "").lower().strip()
    if pref_lang:
        movie_lang = (movie.get("language") or "").lower().strip()
        if movie_lang and movie_lang == pref_lang:
            multiplier += LANG_BOOST
            boost_reasons.append(f"In your preferred language")

    fav_era = user_profile.get("favoriteEra", "")
    era_range = _parse_era(fav_era)
    if era_range:
        movie_year = _get_movie_year(movie)
        if movie_year and era_range[0] <= movie_year <= era_range[1]:
            multiplier += ERA_BOOST
            boost_reasons.append(f"From your favorite era ({fav_era})")

    fav_genre = user_profile.get("favoriteGenre", "").lower().strip()
    if fav_genre:
        movie_genre_ids = _movie_genre_map.get(movie_id, [])
        movie_genre_lower = [_genre_names.get(gid, "").lower() for gid in movie_genre_ids]
        if fav_genre in movie_genre_lower:
            multiplier += GENRE_BOOST
            boost_reasons.append(f"Matches your favorite genre")

    return multiplier, boost_reasons




def get_hybrid_recommendations(user_id, limit=None):
    if not _models_initialized:
        initialize_models()

    limit = limit or DEFAULT_LIMIT

    user_rated = get_user_rated_movies(user_id)
    user_prefs = get_user_preferences(user_id)
    user_watchlist = get_user_watchlist(user_id)
    user_profile = get_user_profile(user_id)

    exclude_ids = set()
    for entry in user_watchlist:
        exclude_ids.add(entry["movie_id"])
    for mid in user_rated:
        exclude_ids.add(mid)

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

    pref_lang = (user_profile.get("preferredLanguage") or "").lower().strip()
    if pref_lang and pref_lang != "en":
        existing_mids = {r["movie_id"] for r in recommendations}
        try:
            lang_movies = tmdb_client.fetch_discover_movies(language=pref_lang, pages=8)
            
            injected_count = 0
            for m in lang_movies:
                mid = m["movie_id"]
                if mid not in existing_mids and mid not in exclude_ids:
                    is_m_regional = (m.get("language") or m.get("original_language") or "").lower() != "en"
                    if not _passes_quality_floor(m, is_regional=True):
                        continue
                    recommendations.append({
                        "movie_id": mid,
                        "score": round(min(m.get("popularity", 0) / 1000.0, 1.0), 4),
                        "reason_type": "language_discovery",
                        "context": {
                            "discovery_lang": pref_lang
                        }
                    })
                    injected_count += 1
                    if mid not in _movies_lookup:
                        _movies_lookup[mid] = m
                        _movie_genre_map[mid] = m.get("genre_ids", [])
            
            if injected_count > 0:
                print(f"[ml-service] Force-injected {injected_count} {pref_lang} movies into candidate pool")
        except Exception as e:
            print(f"[ml-service] WARNING: Language discovery failed for {pref_lang}: {e}")

    recommendations = _apply_preference_boosts(recommendations, user_profile, limit)

    valid_recs = []
    for r in recommendations:
        if isinstance(r, dict) and "movie_id" in r:
            valid_recs.append(r)
        else:
            print(f"[ml-service] WARNING: Dropping invalid recommendation item: {r}")
    
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
    if has_ratings and has_enough_for_collab and collaborative.is_model_built():
        return "hybrid"
    elif has_ratings:
        return "content_only"
    elif has_prefs:
        return "genre_fallback"
    else:
        return "trending_fallback"


def _apply_preference_boosts(results, user_profile, limit):
    pref_lang = (user_profile.get("preferredLanguage") or "").lower().strip()
    fav_era = user_profile.get("favoriteEra", "")
    era_range = _parse_era(fav_era)
    fav_genre = (user_profile.get("favoriteGenre") or "").lower().strip()

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

    active_pref_count = int(bool(pref_lang)) + int(bool(era_range)) + int(bool(fav_genre))
    tiers = {i: [] for i in range(active_pref_count + 1)}

    for rec in results:
        movie = _movies_lookup.get(rec["movie_id"])
        if not movie:
            tiers[0].append(rec)
            continue

        match_count = 0
        boost_reasons = []

        if pref_lang:
            movie_lang = (movie.get("language") or movie.get("original_language") or "").lower().strip()
            if movie_lang == pref_lang:
                match_count += 1
                boost_reasons.append("Language")

        if fav_genre:
            movie_genre_ids = _movie_genre_map.get(rec["movie_id"], [])
            movie_genre_lower = [_genre_names.get(gid, "").lower() for gid in movie_genre_ids]
            if fav_genre in movie_genre_lower:
                match_count += 1
                boost_reasons.append("Genre")

        if era_range:
            movie_year = _get_movie_year(movie)
            if movie_year and era_range[0] <= movie_year <= era_range[1]:
                match_count += 1
                boost_reasons.append("Era")

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

    final_results = []
    print(f"[ml-service] Final Intersection Tiers for {pref_lang}:")
    for s in range(active_pref_count, -1, -1):
        if tiers[s]:
            print(f"  Match Count {s}/{active_pref_count}: {len(tiers[s])} movies")
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

    results_so_far = high_quality
    needed = limit - len(results_so_far)
    
    if needed > 0:
        low_quality = [r for r in final_results if not r.get("context", {}).get("passes_quality_floor")]
        results_so_far.extend(low_quality[:needed])
        
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
                    if m["movie_id"] not in _movies_lookup:
                        _movies_lookup[m["movie_id"]] = m
                        _movie_genre_map[m["movie_id"]] = m.get("genre_ids", [])
        except:
            pass

    return results_so_far[:limit]


def _hybrid_recommend(user_id, user_rated, user_prefs, exclude_ids, limit, user_profile):
    pool_size = limit * 20

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

    results.sort(key=lambda x: -x["score"])
    
    if results:
        langs = {}
        for r in results:
            m = _movies_lookup.get(r["movie_id"], {})
            l = m.get("original_language", "??")
            langs[l] = langs.get(l, 0) + 1
        print(f"[ml-service] Candidate Pool Breakdown by Language: {langs}")
        
    return results[:pool_size]


def _content_only_recommend(user_rated, exclude_ids, limit, user_profile):
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
        
        score_factors = []
        matching_preferences = []

        user_pref_score = sum(user_prefs.get(gid, 0) for gid in genre_ids)
        if user_pref_score > 0:
            score_factors.append(user_pref_score)
            matching_genres = [_genre_names.get(gid, "") for gid in genre_ids if gid in (user_prefs or {})]
            matching_preferences.extend(matching_genres)

        if fav_genre_lower:
            movie_genre_lower = [_genre_names.get(gid, "").lower() for gid in genre_ids]
            if fav_genre_lower in movie_genre_lower:
                score_factors.append(2.0)
                matching_preferences.append(fav_genre_lower.title())

        if pref_lang and pref_lang != "en":
            movie_lang = (movie.get("original_language") or "").lower()
            if movie_lang == pref_lang:
                score_factors.append(1.5)
                matching_preferences.append(f"{pref_lang.upper()} language")

        if pref_era:
            release_year = str(movie.get("release_date", "")).split("-")[0]
            if release_year and _is_era_match(release_year, pref_era):
                score_factors.append(1.0)
                matching_preferences.append(pref_era)

        base_popularity = min(movie.get("popularity", 0) / 1000.0, 3.0)
        if base_popularity > 0:
            score_factors.append(base_popularity)

        final_score = sum(score_factors)

        if final_score > 0:
            scored_movies.append((mid, final_score, genre_ids, matching_preferences, movie))

    scored_movies.sort(key=lambda x: -x[1])

    if not scored_movies:
        return _trending_fallback_recommend(exclude_ids, limit, user_profile)

    max_score = scored_movies[0][1] if scored_movies else 1
    results = []
    for mid, score, genre_ids, matching_prefs, movie in scored_movies[:limit * 3]:
        genre_names = [_genre_names.get(gid, "") for gid in genre_ids if gid in _genre_names]
        
        results.append({
            "movie_id": mid,
            "score": round(score / max_score, 4),
            "reason_type": "genre_intersection",
            "context": {
                "matching_genres": genre_names[:3],
                "matching_preferences": sorted(set(matching_prefs)),
                "genre_count": len([g for g in genre_ids if g in (user_prefs or {})]),
                "language_match": bool(pref_lang and movie.get("original_language", "").lower() == pref_lang),
                "era_match": bool(pref_era and _is_era_match(str(movie.get("release_date", "")).split("-")[0], pref_era))
            }
        })

    return results


def _is_era_match(release_year, era_preference):
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
