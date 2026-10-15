from __future__ import annotations

import copy
import json
import logging
import re
from typing import Iterable, Optional

import litellm

from models.intent import QueryEntities, QueryIntent
from models.query import ConversationState, QueryFilters
from orchestrator.rule_parser import parse_entities, parse_platforms, subject_words

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
                    "discover=browsing by genre/language/decade/rating alone, or trending/popular/top-rated/new releases, "
                    "find_similar=movies like X / similar to X, "
                    "recommend=personalised picks based on user taste, "
                    "search=a specific title, keyword, actor or director, with or without filters, "
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
    "- discover: browsing by genre, language, decade/year or rating alone ('90s crime movies', "
    "'thrillers in tamil', 'science fiction films from the 1990s'); trending, popular, top-rated, new releases, upcoming\n"
    "- find_similar: movies like X, similar to X, in the style of, reminds me of\n"
    "- recommend: personalised recommendations based on the user's taste or history\n"
    "- search: a specific title, keyword, director or actor, even when filters are also given "
    "('batman movies from the 90s' is a search for batman with a year filter)\n"
    "- filter_provider: movies available on a specific streaming platform (Netflix, Prime, etc.)\n"
    "- summarize: reviews, opinions, or ratings for a specific movie\n"
    "- mood_based: movies matching a mood or feeling (funny, scary, feel-good, dark…)\n"
    "- lookup: factual details about a specific movie (cast, runtime, plot, release date, director)"
)


# ── Conversational follow-ups ─────────────────────────────────────────────────

# Constraints a follow-up can drop, and the entity fields each one clears
_REMOVABLE = {
    "genres": ("genres",), "language": ("language",), "years": ("year_from", "year_to"),
    "min_rating": ("min_rating",), "platforms": ("platforms",), "country": ("country",),
    "mood": ("mood",), "seed_movies": ("seed_movies",), "people": ("director", "actor"),
}
_MERGEABLE = (
    "seed_movies", "genres", "country", "platforms", "mood", "director", "actor", "language", "min_rating",
)
_FILTER_FIELDS = ("genres", "language", "year_from", "year_to", "min_rating")

_FOLLOWUP_FIELDS = {
    "refines_previous": {
        "type": "boolean",
        "description": "True if the message refines the previous search, false if it starts a new, unrelated one",
    },
    "exclude_shown": {
        "type": "boolean",
        "description": "True if the user wants more, other or different movies than the ones already shown",
    },
    "removed_constraints": {
        "type": "array",
        "items": {"type": "string", "enum": list(_REMOVABLE)},
        "description": "Constraints of the previous search the user explicitly drops ('any language is fine' -> ['language'])",
    },
}

_FOLLOWUP_PROMPT = (
    "\n\nThe user is in a conversation, and their previous search is shown below. The new message may refine it "
    "('only on Netflix', 'something newer', 'in Hindi instead', 'no horror', 'show me more') or start a new search. "
    "If it refines it, set refines_previous=true and describe the WHOLE updated search: keep the previous intent and "
    "every constraint the user didn't change, list any constraint they drop in removed_constraints, and write "
    "interpreted_as for the full updated search. A platform or a filter on its own doesn't change the intent. "
    "A message with no subject of its own, only a constraint ('from after 2010', 'in hindi', 'under 2 hours', "
    "'only on Netflix'), always refines. "
    "If it names a new subject (another movie, genre, person or mood to search for instead), set "
    "refines_previous=false and ignore the previous search."
)

_MORE = re.compile(r"\b(more|others?|another|different|else)\b")


def _classify_function(followup: bool) -> dict:
    if not followup:
        return _CLASSIFY_FUNCTION
    function = copy.deepcopy(_CLASSIFY_FUNCTION)
    function["parameters"]["properties"].update(_FOLLOWUP_FIELDS)
    function["parameters"]["required"].append("refines_previous")
    return function


def _describe_previous(previous: ConversationState) -> str:
    constraints = previous.entities.model_dump(
        exclude_defaults=True, exclude={"hard_filters", "explicit_platforms", "streaming_filter"},
    )
    return (
        f"\n\nPrevious search: {previous.query!r}\n"
        f"Interpreted as: {previous.interpreted_as}\n"
        f"Intent: {previous.intent}\n"
        f"Constraints: {json.dumps(constraints)}"
    )


def merge_entities(previous: QueryEntities, update: QueryEntities, removed: Iterable[str] = ()) -> QueryEntities:
    """The previous turn's constraints, overridden by what this turn sets and minus what it drops.

    The LLM is asked for the whole updated search, but a model that forgets to carry a
    constraint over would silently widen the search, so anything it leaves empty is kept.
    """
    dropped = {field for name in removed for field in _REMOVABLE.get(name, ())}
    merged = previous.model_copy(deep=True)
    for field in _MERGEABLE:
        value = getattr(update, field)
        if value not in (None, "", []):
            setattr(merged, field, value)
        elif field in dropped:
            setattr(merged, field, [] if isinstance(value, list) else None)
    # A year range is one constraint: "after 2015" replaces both ends, not just year_from
    if update.year_from or update.year_to:
        merged.year_from, merged.year_to = update.year_from, update.year_to
    elif "year_from" in dropped:
        merged.year_from = merged.year_to = None
    return merged


def _refined_flags(entities: QueryEntities, previous: QueryEntities) -> None:
    """Constraints added in a follow-up are deliberate: enforce them whatever the intent."""
    changed = any(getattr(entities, f) != getattr(previous, f) for f in _FILTER_FIELDS)
    entities.hard_filters = bool(previous.hard_filters or changed) and any(
        getattr(entities, f) not in (None, []) for f in _FILTER_FIELDS
    )
    if entities.platforms:
        # "only on Netflix" is the whole point of such a message, so match the platform for real
        entities.streaming_filter = entities.explicit_platforms = True
    else:
        entities.streaming_filter = entities.explicit_platforms = False


async def _call_classifier(query: str, temperature: float, previous: Optional[ConversationState] = None) -> dict:
    system = _SYSTEM_PROMPT + (_FOLLOWUP_PROMPT + _describe_previous(previous) if previous else "")
    response = await litellm.acompletion(
        model=_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": query},
        ],
        tools=[{"type": "function", "function": _classify_function(previous is not None)}],
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
    previous: Optional[ConversationState] = None,
) -> QueryIntent:
    # The model occasionally emits malformed tool-call JSON (Groq "tool_use_failed").
    # Retry once with a little temperature (temperature 0 would repeat the same output).
    data: Optional[dict] = None
    for temperature in (0, 0.3):
        try:
            data = await _call_classifier(query, temperature, previous)
            break
        except (litellm.BadRequestError, json.JSONDecodeError, RuntimeError) as exc:
            logger.warning("Intent classification attempt failed (T=%s): %s", temperature, str(exc)[:200])
        except Exception as exc:
            # Rate limit, timeout, outage: an immediate retry would fail the same way
            logger.warning("Intent classification unavailable: %s", str(exc)[:200])
            break

    if data is None:
        return _fallback_intent(query, user_context, previous)

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
    refines = bool(previous and data.get("refines_previous"))
    if refines:
        entities = merge_entities(previous.entities, entities, data.get("removed_constraints") or [])
        _refined_flags(entities, previous.entities)
    elif data["primary_intent"] in _CONSTRAINED_INTENTS:
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
        refines_previous=refines,
        exclude_shown=refines and bool(data.get("exclude_shown")),
    )


def _fallback_followup(query: str, previous: ConversationState, personalized: bool) -> Optional[QueryIntent]:
    """LLM unavailable mid-conversation: if the message reads as filters ("in hindi", "only on
    netflix") or a request for more, apply it to the previous search; otherwise it's a new one."""
    text = " ".join(query.lower().split())
    if subject_words(text):
        return None     # names something of its own ("what about star wars"): a new search
    update = parse_entities(text)
    update.platforms = parse_platforms(text)
    wants_more = bool(_MORE.search(text))
    if not (wants_more or update.platforms or any(getattr(update, f) not in (None, []) for f in _FILTER_FIELDS)):
        return None

    entities = merge_entities(previous.entities, update)
    _refined_flags(entities, previous.entities)
    return QueryIntent(
        primary_intent=previous.intent,
        entities=entities,
        complexity="simple",
        interpreted_as=f"{previous.interpreted_as} ({query.strip()[:80]})",
        requires_personalization=personalized,
        degraded=True,
        refines_previous=True,
        exclude_shown=wants_more,
    )


def _fallback_intent(
    query: str, user_context: Optional[dict] = None, previous: Optional[ConversationState] = None,
) -> QueryIntent:
    """LLM unavailable: a keyword search that still enforces the filters the rule parser can
    read, so "90s crime movies" returns 90s crime movies rather than titles containing "crime".

    Only when the filters are the whole query, though: in "star wars" or "the french connection"
    the filter words are part of a title, and enforcing them would filter the title out."""
    personalized = bool(user_context and user_context.get("user_id"))
    if previous:
        followup = _fallback_followup(query, previous, personalized)
        if followup:
            return followup

    entities = QueryEntities() if subject_words(query) else parse_entities(query)
    entities.hard_filters = bool(
        entities.genres or entities.language or entities.year_from or entities.min_rating is not None
    )
    return QueryIntent(
        primary_intent="search",
        entities=entities,
        complexity="simple",
        interpreted_as=query[:80],
        requires_personalization=personalized,
        degraded=True,
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
