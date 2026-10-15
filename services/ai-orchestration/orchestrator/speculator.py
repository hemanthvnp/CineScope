"""
Speculative prefetch — guesses the TMDB calls a query needs *before* the LLM answers.

A cheap rule-based parse pulls out the unambiguous parts of a query (genres, a decade or
year, a language, "rated above N", "movies like X") and runs them through the real tool
planner, so a correct guess produces exactly the params the LLM-driven plan will. The
engine runs the guess in the background while the LLM classifies the query; the real
plan then finds those results in the tool cache (or joins the call still in flight).

A wrong guess costs one or two extra TMDB calls and nothing else. Anything ambiguous
("after 2015", "highly rated", moods) is left to the LLM rather than guessed.
"""
from __future__ import annotations

import re
from typing import Optional

from models.intent import ExecutionPlan, QueryIntent
from models.query import QueryFilters
from orchestrator.intent_classifier import apply_filters
from orchestrator.rule_parser import parse_entities
from orchestrator.tool_planner import build_plan

_SIMILAR = re.compile(r"^(?:movies?|films?|something|anything)?\s*(?:like|similar to)\s+([^,]+?)(?:\s+but\b.*)?$")


def guess_plan(query: str, filters: Optional[QueryFilters] = None, max_results: int = 10) -> Optional[ExecutionPlan]:
    """The TMDB calls the real plan will most likely contain, or None when there's nothing safe to guess."""
    text = " ".join(query.lower().split()).rstrip("?!.")

    similar = _SIMILAR.match(text)
    if similar:
        intent = QueryIntent(primary_intent="find_similar", interpreted_as=text)
        intent.entities.seed_movies = [similar.group(1)]
        plan = build_plan(intent, max_results=max_results)
        # resolve_seed → tmdb_similar; the semantic node depends on LLM wording, so skip it
        nodes = [n for n in plan.nodes if n.id in ("resolve_seed", "tmdb_sim")]
        return ExecutionPlan(nodes=nodes)

    entities = parse_entities(text)
    has_filters = bool(entities.genres or entities.language or entities.year_from or entities.min_rating is not None)
    if not has_filters and not (filters and filters.is_active()):
        return None

    entities.hard_filters = has_filters
    intent = apply_filters(QueryIntent(primary_intent="search", entities=entities, interpreted_as=text), filters)
    plan = build_plan(intent, max_results=max_results)
    # Only the filtered discover call is predictable; search/semantic queries use LLM wording
    nodes = [n for n in plan.nodes if n.tool == "tmdb_discover"]
    return ExecutionPlan(nodes=nodes) if nodes else None
