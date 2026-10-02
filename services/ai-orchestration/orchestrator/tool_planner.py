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
    genre_text = " ".join(g for g in entities.genres if not str(g).isdigit())  # ids are meaningless in prompts
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
                params={"query": genre_text + " movies", "k": max_results * 2},
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
                "query": f"movies similar to {seed} {genre_text}",
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
        mood_query = f"{entities.mood or ''} {genre_text} movies".strip()
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

    _apply_filters_to_plan(nodes, intent, max_results)

    return ExecutionPlan(nodes=nodes, merge_strategy=primary)


_FILTERABLE_INTENTS = {"discover", "search", "recommend", "mood_based", "filter_provider", "find_similar"}


def _apply_filters_to_plan(nodes: list[PlanNode], intent: QueryIntent, max_results: int) -> None:
    """Make every candidate-producing intent honour genre/language/year/rating filters.

    Explicit filters (hard_filters) guarantee a filtered tmdb_discover node exists, so
    the pool is built from matching movies rather than hoping the other tools return some.
    """
    e = intent.entities
    if intent.primary_intent not in _FILTERABLE_INTENTS:
        return

    filter_params = {
        "genres": e.genres,
        "year_from": e.year_from,
        "year_to": e.year_to,
        "language": e.language,
        "min_rating": e.min_rating,
    }
    has_filters = bool(e.genres or e.year_from or e.year_to or e.language or e.min_rating is not None)
    if not has_filters:
        return

    discover = next((n for n in nodes if n.tool == "tmdb_discover"), None)
    if discover:
        discover.params.update({k: v for k, v in filter_params.items() if v})
    elif e.hard_filters:
        discover = PlanNode(id="discover", tool="tmdb_discover", params={**filter_params, "limit": max_results * 5})
        nodes.append(discover)
    if discover:
        discover.params["limit"] = max(discover.params.get("limit", 0), max_results * 5)

    if e.hard_filters and intent.primary_intent == "discover":
        # Unfiltered trending would just be thrown away by the hard filter
        nodes[:] = [n for n in nodes if n.tool != "tmdb_trending"]
