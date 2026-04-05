


def generate_explanation(movie, reason_type, context=None):
    context = context or {}

    if reason_type == "content":
        source = context.get("source_movie_title", "your favorites")
        return {
            "reason": f"Because you liked {source}",
            "type": "content_similarity"
        }

    elif reason_type == "collaborative":
        user_count = context.get("similar_users_count", 0)
        if user_count > 1:
            return {
                "reason": f"Popular among {user_count} similar users",
                "type": "collaborative"
            }
        return {
            "reason": "Popular among similar users",
            "type": "collaborative"
        }

    elif reason_type == "genre_intersection":
        matching_prefs = context.get("matching_preferences", [])
        if matching_prefs:
            return {
                "reason": f"Matches your {', '.join(matching_prefs[:2])}",
                "type": "genre_match"
            }
        return {
            "reason": "Based on your profile preferences",
            "type": "genre_match"
        }

    elif reason_type == "genre":
        genres = context.get("genres", [])
        if genres:
            return {
                "reason": f"Matches your interest in {', '.join(genres[:3])}",
                "type": "genre_match"
            }
        return {
            "reason": "Based on your genre preferences",
            "type": "genre_match"
        }

    elif reason_type == "trending":
        return {
            "reason": "Trending this week",
            "type": "trending"
        }

    elif reason_type == "hybrid":
        collab_score = context.get("collab_score", 0)
        content_score = context.get("content_score", 0)
        
        if collab_score > content_score:
            return {
                "reason": "Similar users with similar taste also liked this",
                "type": "collaborative"
            }
        else:
            source = context.get("source_movie_title", "your favorites")
            return {
                "reason": f"Because you liked {source}",
                "type": "content_similarity"
            }

    elif reason_type == "language_discovery":
        lang = context.get("discovery_lang", "your preferred language")
        return {
            "reason": f"Popular in {lang.upper()} cinema",
            "type": "language_preference"
        }

    else:
        return {
            "reason": "Recommended for you",
            "type": "general"
        }


def explain_batch(recommendations, movies_lookup, genre_names, movie_genre_map):
    for rec in recommendations:
        movie_id = rec["movie_id"]
        context = rec.get("context", {})
        if not isinstance(context, dict):
            context = {}

        genre_ids = movie_genre_map.get(movie_id, [])
        context["genres"] = [genre_names.get(gid, "") for gid in genre_ids if gid in genre_names]

        source_mid = context.get("source_movie_id")
        if source_mid and source_mid in movies_lookup:
            context["source_movie_title"] = movies_lookup[source_mid]["title"]

        reason_type = rec.get("reason_type", "hybrid")
        explanation = generate_explanation(
            movies_lookup.get(movie_id, {}),
            reason_type,
            context
        )

        intersection_reasons = context.get("intersection_reasons", [])
        
        if intersection_reasons:
            if not isinstance(explanation, dict):
                print(f"[ml-service] ERROR: explanation is not a dict! type={type(explanation)}, val={explanation}, rec={rec}")
                explanation = {"reason": "Recommended for you", "type": "general"}
            
            if len(intersection_reasons) == 3:
                explanation["boost"] = f"Matches {intersection_reasons[0]}, {intersection_reasons[1]}, and {intersection_reasons[2]}"
            elif len(intersection_reasons) == 2:
                explanation["boost"] = f"Matches {intersection_reasons[0]} and {intersection_reasons[1]}"
            else:
                explanation["boost"] = f"Matches {intersection_reasons[0]}"

        rec["explanation"] = explanation

    return recommendations

