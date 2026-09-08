from __future__ import annotations

import json
from typing import Optional

import litellm

from models.intent import QueryEntities, QueryIntent

_MODEL = "groq/openai/gpt-oss-20b"


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


async def classify_intent(
    query: str,
    user_context: Optional[dict] = None,
) -> QueryIntent:
    response = await litellm.acompletion(
        model=_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        tools=[{"type": "function", "function": _CLASSIFY_FUNCTION}],
        tool_choice={"type": "function", "function": {"name": "classify_intent"}},
        max_tokens=512,
        temperature=0,
        reasoning_effort="low",
    )

    message = response.choices[0].message
    if not message.tool_calls:
        raise RuntimeError(f"litellm returned no function call for query: {query!r}")

    data: dict = json.loads(message.tool_calls[0].function.arguments)

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


def classify_intent_sync(query: str, user_context: Optional[dict] = None) -> QueryIntent:
    """Synchronous wrapper — for tests and debug only."""
    import asyncio
    return asyncio.run(classify_intent(query, user_context))
