"""
Tool planner — maps a QueryIntent to an ExecutionPlan (a DAG of PlanNodes).

Rules:
  • Nodes with no dependencies run in Phase 1 (fully parallel).
  • Nodes that depend on other nodes run after their deps complete.
  • Optional nodes don't block execution if they fail.
  • Providers are NOT in the DAG; the aggregator fetches them after ranking.
"""
from __future__ import annotations

from models.intent import ExecutionPlan, PlanNode, QueryIntent


def build_plan(
    intent: QueryIntent,
    user_id: str | None = None,
    locale: str = "US",
    max_results: int = 10,
) -> ExecutionPlan:
    nodes: list[PlanNode] = []
    entities = intent.entities
    primary = intent.primary_intent

    # ── discover ──────────────────────────────────────────────────────────────
    if primary == "discover":
        nodes.append(PlanNode(
            id="trending",
            tool="tmdb_trending",
            params={"limit": max_results * 3},
        ))
        if entities.genres:
            nodes.append(PlanNode(
                id="discover",
                tool="tmdb_discover",
                params={
                    "genres": entities.genres,
                    "year_from": entities.year_from,
                    "year_to": entities.year_to,
                    "limit": max_results * 3,
                },
            ))
            nodes.append(PlanNode(
                id="semantic",
                tool="semantic_search",
                params={"query": " ".join(entities.genres) + " movies", "k": max_results * 2},
            ))

    # ── find_similar ──────────────────────────────────────────────────────────
    elif primary == "find_similar":
        seed = entities.seed_movies[0] if entities.seed_movies else ""
        # Resolve seed movie → get TMDB ID
        nodes.append(PlanNode(
            id="resolve_seed",
            tool="tmdb_search",
            params={"query": seed, "limit": 1},
        ))
        # TMDB's own "similar" endpoint (needs resolve_seed result)
        nodes.append(PlanNode(
            id="tmdb_sim",
            tool="tmdb_similar",
            params={"limit": max_results * 2},
            dependencies=["resolve_seed"],
            optional=True,
        ))
        # Semantic similarity runs in parallel with resolve_seed
        nodes.append(PlanNode(
            id="semantic",
            tool="semantic_search",
            params={
                "query": f"movies similar to {seed} {' '.join(entities.genres)}",
                "k": max_results * 3,
            },
        ))

    # ── recommend ─────────────────────────────────────────────────────────────
    elif primary == "recommend":
        if user_id:
            nodes.append(PlanNode(
                id="user_data",
                tool="user_profile",
                params={"user_id": user_id},
            ))
            nodes.append(PlanNode(
                id="ml_recs",
                tool="ml_recommend",
                params={"user_id": user_id, "limit": max_results * 2},
                optional=True,
            ))
        nodes.append(PlanNode(
            id="semantic",
            tool="semantic_search",
            params={"query": intent.interpreted_as, "k": max_results * 2},
        ))
        nodes.append(PlanNode(
            id="trending",
            tool="tmdb_trending",
            params={"limit": max_results * 2},
        ))

    # ── search ────────────────────────────────────────────────────────────────
    elif primary == "search":
        search_q = intent.interpreted_as
        if entities.director:
            search_q = f"{entities.director} movies"
        elif entities.actor:
            search_q = f"{entities.actor} movies"
        nodes.append(PlanNode(
            id="tmdb_search",
            tool="tmdb_search",
            params={
                "query": search_q,
                "year": entities.year_from,
                "limit": max_results * 2,
            },
        ))
        nodes.append(PlanNode(
            id="semantic",
            tool="semantic_search",
            params={"query": intent.interpreted_as, "k": max_results},
        ))

    # ── filter_provider ───────────────────────────────────────────────────────
    elif primary == "filter_provider":
        # Get a large pool — the aggregator will filter by provider availability
        nodes.append(PlanNode(
            id="discover",
            tool="tmdb_discover",
            params={
                "genres": entities.genres,
                "limit": max(max_results * 5, 50),   # over-fetch for provider filter
            },
        ))
        if entities.seed_movies:
            nodes.append(PlanNode(
                id="semantic",
                tool="semantic_search",
                params={"query": intent.interpreted_as, "k": max_results * 3},
            ))
        nodes.append(PlanNode(
            id="trending",
            tool="tmdb_trending",
            params={"limit": max_results * 2},
        ))

    # ── summarize ─────────────────────────────────────────────────────────────
    elif primary == "summarize":
        movie_title = entities.seed_movies[0] if entities.seed_movies else ""
        nodes.append(PlanNode(
            id="resolve_movie",
            tool="tmdb_search",
            params={"query": movie_title, "limit": 1},
        ))
        nodes.append(PlanNode(
            id="movie_details",
            tool="tmdb_movie_details",
            params={},
            dependencies=["resolve_movie"],
        ))
        nodes.append(PlanNode(
            id="reviews",
            tool="movie_reviews",
            params={},
            dependencies=["resolve_movie"],
        ))
        intent.requires_synthesis = True

    # ── mood_based ────────────────────────────────────────────────────────────
    elif primary == "mood_based":
        mood_query = f"{entities.mood or ''} {' '.join(entities.genres)} movies".strip()
        nodes.append(PlanNode(
            id="semantic",
            tool="semantic_search",
            params={"query": mood_query, "k": max_results * 3},
        ))
        nodes.append(PlanNode(
            id="discover",
            tool="tmdb_discover",
            params={"genres": entities.genres, "limit": max_results * 2},
        ))

    # ── lookup ────────────────────────────────────────────────────────────────
    elif primary == "lookup":
        movie_title = entities.seed_movies[0] if entities.seed_movies else ""
        nodes.append(PlanNode(
            id="resolve_movie",
            tool="tmdb_search",
            params={"query": movie_title, "limit": 1},
        ))
        nodes.append(PlanNode(
            id="movie_details",
            tool="tmdb_movie_details",
            params={},
            dependencies=["resolve_movie"],
        ))
        intent.requires_synthesis = True

    return ExecutionPlan(nodes=nodes, merge_strategy=primary)
