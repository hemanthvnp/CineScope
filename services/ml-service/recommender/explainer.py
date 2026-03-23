"""
CineScope ML Service — Explainability Module

Generates human-readable explanations for each recommendation.
This is critical for user trust — users engage more with recommendations
they can understand the reasoning behind.

Explanation types:
1. "Because you liked [Movie]" — from content-based similarity
2. "Similar genres: Sci-Fi, Drama" — from genre overlap
3. "Popular among similar users" — from collaborative filtering signal
4. "Trending this week" — for popularity-based fallback
"""


def generate_explanation(movie, reason_type, context=None):
    """
    Generate an explanation for why a movie is recommended.

    Args:
        movie: dict with movie_id, title, etc.
        reason_type: one of 'content', 'collaborative', 'genre', 'trending', 'hybrid'
        context: additional context dict, may include:
            - source_movie_title: title of the movie this is similar to
            - genres: list of matching genre names
            - similar_users_count: number of similar users
            - content_score: raw content score
            - collab_score: raw collaborative score

    Returns:
        dict with 'reason' (display string) and 'type' (explanation category)
    """
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

    elif reason_type == "genre":
        genres = context.get("genres", [])
        if genres:
            genre_str = ", ".join(genres[:3])
            return {
                "reason": f"Similar genres: {genre_str}",
                "type": "genre_match"
            }
        return {
            "reason": "Matches your genre preferences",
            "type": "genre_match"
        }

    elif reason_type == "trending":
        return {
            "reason": "Trending this week",
            "type": "trending"
        }

    elif reason_type == "hybrid":
        # Determine the dominant signal for the explanation
        content_score = context.get("content_score", 0)
        collab_score = context.get("collab_score", 0)

        if content_score > collab_score and context.get("source_movie_title"):
            return {
                "reason": f"Because you liked {context['source_movie_title']}",
                "type": "content_similarity"
            }
        elif collab_score > 0:
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
        else:
            genres = context.get("genres", [])
            if genres:
                return {
                    "reason": f"Similar genres: {', '.join(genres[:3])}",
                    "type": "genre_match"
                }
            return {
                "reason": "Recommended for you",
                "type": "general"
            }

    return {
        "reason": "Recommended for you",
        "type": "general"
    }


def explain_batch(recommendations, movies_lookup, genre_names, movie_genre_map):
    """
    Add explanation context to a batch of recommendations.
    Also integrates intersection boost reasons into the explanation.
    """
    for rec in recommendations:
        movie_id = rec["movie_id"]
        context = rec.get("context", {})
        if not isinstance(context, dict):
            context = {}

        # Enrich context with genre names
        genre_ids = movie_genre_map.get(movie_id, [])
        context["genres"] = [genre_names.get(gid, "") for gid in genre_ids if gid in genre_names]

        # Add source movie title if we have a content match
        source_mid = context.get("source_movie_id")
        if source_mid and source_mid in movies_lookup:
            context["source_movie_title"] = movies_lookup[source_mid]["title"]

        # Generate primary explanation
        reason_type = rec.get("reason_type", "hybrid")
        explanation = generate_explanation(
            movies_lookup.get(movie_id, {}),
            reason_type,
            context
        )

        # Append intersection tier logic to the explanation
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

