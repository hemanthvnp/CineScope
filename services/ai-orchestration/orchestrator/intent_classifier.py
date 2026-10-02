from __future__ import annotations

import json
import logging
from typing import Optional

import litellm

from models.intent import QueryEntities, QueryIntent
from models.query import QueryFilters

_MODEL = "groq/openai/gpt-oss-20b"

logger = logging.getLogger(__name__)


_CONSTRAINED_INTENTS = {"discover", "search", "recommend", "mood_based", "filter_provider"}

_CLASSIFY_FUNCTION = {
    "name": "classify_intent",
    "description": "Classify a movie-related natural language query into a structured intent with extracted entities.",
    "parameters": {
        "type": "object",
        "properties": {
            "primary_intent": {
                "type": "string",
                "enum": [
                    "discover", "find_similar", "recommend", "search",
                    "filter_provider", "summarize", "mood_based", "lookup",
                ],
                "description": (
                    "The primary user intent. "
                    "discover=trending/popular/top-rated/new releases, "
                    "find_similar=movies like X / similar to X, "
                    "recommend=personalised picks based on user taste, "
                    "search=general keyword/title/actor/director search, "
                    "filter_provider=available on a specific streaming service, "
                    "summarize=reviews or opinions about a specific movie, "
                    "mood_based=movies matching a mood or feeling, "
                    "lookup=factual details about a movie (cast, runtime, plot, release date)"
                ),
            },
            "seed_movies": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Movie titles explicitly mentioned (e.g. ['Inception', 'Fight Club'])",
            },
            "genres": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Genres mentioned (e.g. ['action', 'sci-fi', 'thriller'])",
            },
            "country": {
                "type": "string",
                "description": "ISO 2-letter country code if a region is specified (e.g. IN, KR, US, GB)",
            },
            "year_from": {
                "type": "integer",
                "description": "Start year if a year range or decade is mentioned",
            },
            "year_to": {
                "type": "integer",
                "description": "End year of a range; same as year_from for a single year",
            },
            "language": {
                "type": "string",
                "description": "Original language as ISO 639-1 code if mentioned (e.g. hi for Hindi, ko for Korean, ja for Japanese)",
            },
            "min_rating": {
                "type": "number",
                "description": "Minimum TMDB rating (0-10) if the user asks for highly rated / above N",
            },
            "platforms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Streaming platforms mentioned (e.g. ['Netflix', 'Disney+', 'Prime Video'])",
            },
            "mood": {
                "type": "string",
                "description": "Mood or feeling expressed (e.g. funny, scary, feel-good, dark, intense)",
            },
            "director": {
                "type": "string",
                "description": "Director name if explicitly mentioned",
            },
            "actor": {
                "type": "string",
                "description": "Actor name if explicitly mentioned",
            },
            "requires_personalization": {
                "type": "boolean",
                "description": "True if the query asks for recommendations tailored to the user's personal taste",
            },
            "requires_synthesis": {
                "type": "boolean",
                "description": "True if the query needs synthesising information (reviews, summaries, details)",
            },
            "complexity": {
                "type": "string",
                "enum": ["simple", "medium", "complex"],
                "description": (
                    "simple = single clear intent, "
                    "medium = multiple filters or constraints, "
                    "complex = synthesis / multi-step reasoning needed"
                ),
            },
            "interpreted_as": {
                "type": "string",
                "description": (
                    "Short human-readable interpretation of what the user is looking for "
                    "(e.g. 'Movies similar to Inception — genre: sci-fi')"
                ),
            },
        },
        "required": ["primary_intent", "interpreted_as"],
    },
}

_SYSTEM_PROMPT = (
    "You are a movie query classifier for CineScope, a movie discovery platform. "
    "Parse the user's natural language query and call the classify_intent function with the structured result.\n\n"
    "Intent types:\n"
    "- discover: trending, popular, top-rated, new releases, upcoming\n"
    "- find_similar: movies like X, similar to X, in the style of, reminds me of\n"
    "- recommend: personalised recommendations based on the user's taste or history\n"
    "- search: general search by title, director, actor, or keyword\n"
    "- filter_provider: movies available on a specific streaming platform (Netflix, Prime, etc.)\n"
    "- summarize: reviews, opinions, or ratings for a specific movie\n"
    "- mood_based: movies matching a mood or feeling (funny, scary, feel-good, dark…)\n"
    "- lookup: factual details about a specific movie (cast, runtime, plot, release date, director)"
)


async def _call_classifier(query: str, temperature: float) -> dict:
    response = await litellm.acompletion(
        model=_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        tools=[{"type": "function", "function": _CLASSIFY_FUNCTION}],
        tool_choice={"type": "function", "function": {"name": "classify_intent"}},
        max_tokens=512,
        temperature=temperature,
        reasoning_effort="low",
    )
    message = response.choices[0].message
    if not message.tool_calls:
        raise RuntimeError(f"litellm returned no function call for query: {query!r}")
    return json.loads(message.tool_calls[0].function.arguments)


async def classify_intent(
    query: str,
    user_context: Optional[dict] = None,
) -> QueryIntent:
    # The model occasionally emits malformed tool-call JSON (Groq "tool_use_failed").
    # Retry once with a little temperature (temperature 0 would repeat the same output).
    data: Optional[dict] = None
    for temperature in (0, 0.3):
        try:
            data = await _call_classifier(query, temperature)
            break
        except (litellm.BadRequestError, json.JSONDecodeError, RuntimeError) as exc:
            logger.warning("Intent classification attempt failed (T=%s): %s", temperature, str(exc)[:200])

    if data is None:
        # Degrade to a plain search instead of failing the request
        return QueryIntent(
            primary_intent="search",
            complexity="simple",
            interpreted_as=query[:80],
            requires_personalization=bool(user_context and user_context.get("user_id")),
        )

    entities = QueryEntities(
        seed_movies=data.get("seed_movies") or [],
        genres=data.get("genres") or [],
        country=data.get("country"),
        year_from=data.get("year_from"),
        year_to=data.get("year_to"),
        streaming_filter=bool(data.get("platforms")),
        platforms=data.get("platforms") or [],
        mood=data.get("mood"),
        director=data.get("director"),
        actor=data.get("actor"),
        language=data.get("language"),
        min_rating=data.get("min_rating"),
    )

    # "best thriller tamil movies" means Tamil AND thriller: enforce what the user asked for.
    # find_similar is excluded: genres there are hints around a seed movie, not constraints.
    if data["primary_intent"] in _CONSTRAINED_INTENTS:
        entities.hard_filters = bool(
            entities.genres or entities.language or entities.year_from
            or entities.year_to or entities.min_rating is not None
        )

    requires_personalization = bool(data.get("requires_personalization"))
    if user_context and user_context.get("user_id"):
        requires_personalization = True

    return QueryIntent(
        primary_intent=data["primary_intent"],
        entities=entities,
        requires_personalization=requires_personalization,
        requires_synthesis=bool(data.get("requires_synthesis")),
        complexity=data.get("complexity", "medium"),
        interpreted_as=data.get("interpreted_as", query[:80]),
    )


def filter_only_intent(filters: Optional[QueryFilters] = None) -> QueryIntent:
    """No text query: skip the LLM call and treat the filters as a discover request."""
    return QueryIntent(
        primary_intent="discover",
        complexity="medium",
        interpreted_as="Movies matching the selected filters",
    )


def apply_filters(intent: QueryIntent, filters: Optional[QueryFilters]) -> QueryIntent:
    """Merge explicit filters into the LLM-extracted intent.

    Explicit filters win over anything the LLM inferred from the text, and any
    combination of them is enforced as a hard constraint downstream.
    """
    if not filters or not filters.is_active():
        return intent

    e = intent.entities
    if filters.genres:
        e.genres = list(filters.genres)
    if filters.language:
        e.language = filters.language
    if filters.min_rating is not None:
        e.min_rating = filters.min_rating
    year_from, year_to = filters.year_range()
    if year_from or year_to:
        e.year_from, e.year_to = year_from, year_to
    if filters.platforms:
        e.platforms = list(filters.platforms)
        e.streaming_filter = True
        e.explicit_platforms = True
    if filters.country:
        e.country = filters.country
    e.hard_filters = True

    parts = [
        ", ".join(filters.genres) if filters.genres else "",
        f"language {filters.language}" if filters.language else "",
        f"{year_from}-{year_to}" if year_from and year_to and year_from != year_to
        else str(year_from or year_to or ""),
        f"rating >= {filters.min_rating}" if filters.min_rating is not None else "",
        f"on {', '.join(filters.platforms)}" if filters.platforms else "",
    ]
    applied = "; ".join(p for p in parts if p)
    intent.interpreted_as = f"{intent.interpreted_as} [filters: {applied}]"
    return intent


def classify_intent_sync(query: str, user_context: Optional[dict] = None) -> QueryIntent:
    """Synchronous wrapper — for tests and debug only."""
    import asyncio
    return asyncio.run(classify_intent(query, user_context))
