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
from tools.tmdb_tool import _GENRE_IDS, genre_ids

_GENRE_NAMES: dict[int, str] = {}
for _name, _gid in _GENRE_IDS.items():
    _GENRE_NAMES.setdefault(_gid, _name)


def _genre_text(genres: list) -> str:
    """Genres as prompt text in one spelling and order ("Science Fiction", "sci-fi" → "sci-fi")."""
    names = {_GENRE_NAMES.get(gid) for gid in genre_ids(genres)}
    names |= {str(g).lower() for g in genres if not str(g).isdigit() and not genre_ids([g])}
    return " ".join(sorted(n for n in names if n))


def build_plan(
    intent: QueryIntent,
    user_id: str | None = None,
    locale: str = "US",
    max_results: int = 10,
) -> ExecutionPlan:
    nodes: list[PlanNode] = []
    entities = intent.entities
    genre_text = _genre_text(entities.genres)
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
        seed = entities.seed_movies[0].strip() if entities.seed_movies else ""
        # Resolve seed movie → get TMDB ID (TMDB search ignores case; lowercase keeps the cache key stable)
        nodes.append(PlanNode(
            id="resolve_seed",
            tool="tmdb_search",
            params={"query": seed.lower(), "limit": 1},
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
    elif primary == "search" and (entities.director or entities.actor):
        # Only their filmography: semantic search or trending would add unrelated popular
        # movies, and those outrank the person's own films in the merged pool
        role = "director" if entities.director else "actor"
        nodes.append(PlanNode(
            id="person",
            tool="tmdb_person_movies",
            params={
                # Lowercase keeps the cache key stable, as for resolve_seed
                "name": (entities.director or entities.actor).strip().lower(),
                "role": role,
                "limit": max_results * 3,
            },
        ))

    elif primary == "search":
        search_q = intent.interpreted_as
        nodes.append(PlanNode(
            id="tmdb_search",
            tool="tmdb_search",
            params={
                "query": search_q,
                # TMDB's `year` is one exact year: passing the start of a range ("batman movies
                # from the 90s" → 1990) would drop everything released later in it
                "year": entities.year_from if entities.year_from == entities.year_to else None,
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

    # Canonical form ("Sci-Fi" / "science fiction" / "878" → [878], 8 → 8.0) so equivalent
    # queries produce identical params, and therefore share tool-cache entries
    filter_params = {
        "genres": sorted(set(genre_ids(e.genres))),
        "year_from": e.year_from,
        "year_to": e.year_to,
        "language": e.language.lower() if e.language else None,
        "min_rating": float(e.min_rating) if e.min_rating is not None else None,
    }
    has_filters = bool(e.genres or e.year_from or e.year_to or e.language or e.min_rating is not None)
    if not has_filters:
        return

    person = next((n for n in nodes if n.tool == "tmdb_person_movies"), None)
    if person:
        # Filter the filmography itself; a filtered discover would add other people's movies
        person.params.update({k: v for k, v in filter_params.items() if v})
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
