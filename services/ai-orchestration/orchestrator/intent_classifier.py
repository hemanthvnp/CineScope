"""
Rule-based intent classifier — zero API cost, deterministic, ~0ms latency.

Covers all eight intent types via keyword/pattern matching.
Entity extraction uses regex for countries, years, genre names, and movie titles.
"""
from __future__ import annotations

import re
from typing import Optional

from models.intent import QueryEntities, QueryIntent

# ── Keyword tables ─────────────────────────────────────────────────────────────

_SIMILAR_KWS   = {"similar to", "like", "reminds me of", "in the style of",
                   "movies like", "films like", "something like", "just like"}
_RECOMMEND_KWS = {"recommend", "suggest", "what should i watch", "what to watch",
                   "for me", "my taste", "i'd enjoy", "i would enjoy", "pick for me",
                   "personalised", "personalized"}
_SUMMARIZE_KWS = {"summarize", "summarise", "summary", "reviews of", "review of",
                   "what do people think", "is it good", "worth watching",
                   "opinions on", "rating for", "ratings for"}
_LOOKUP_KWS    = {"runtime", "cast", "director", "who directed", "budget",
                   "plot of", "synopsis of", "when was", "release date",
                   "how long is", "imdb", "starring"}
_DISCOVER_KWS  = {"trending", "popular", "top movies", "best movies", "new releases",
                   "latest movies", "what's new", "whats new", "top rated",
                   "most watched", "now playing", "upcoming", "coming soon"}
_MOOD_KWS      = {"feel-good", "feel good", "funny", "laugh", "cheer me up",
                   "scared", "scary", "dark", "intense", "relax", "light-hearted",
                   "emotional", "cry", "inspiring", "motivating", "mind-blowing",
                   "thought-provoking", "in the mood", "mood"}
_PROVIDER_KWS  = {"netflix", "prime", "amazon", "hulu", "disney", "apple tv",
                   "hbo", "peacock", "paramount", "streaming", "streamable",
                   "available on", "watch on", "where can i watch"}

_GENRES = {
    "action", "adventure", "animation", "comedy", "crime", "documentary",
    "drama", "family", "fantasy", "history", "horror", "music", "mystery",
    "romance", "sci-fi", "science fiction", "thriller", "war", "western",
}

_COUNTRY_MAP = {
    "india": "IN", "indian": "IN", "bollywood": "IN",
    "us": "US", "usa": "US", "america": "US", "american": "US",
    "uk": "GB", "britain": "GB", "british": "GB",
    "korea": "KR", "korean": "KR",
    "japan": "JP", "japanese": "JP",
    "france": "FR", "french": "FR",
    "germany": "DE", "german": "DE",
    "spain": "ES", "spanish": "ES",
    "italy": "IT", "italian": "IT",
    "china": "CN", "chinese": "CN",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def _lower(q: str) -> str:
    return q.lower()


def _contains_any(text: str, keywords: set) -> bool:
    for kw in keywords:
        if kw in text:
            return True
    return False


_TITLE_STOP_WORDS = {
    "streaming", "streamable", "available", "and", "but", "or", "that",
    "which", "with", "where", "when", "genre", "genres", "release", "year",
    "directed", "starring", "rated", "featuring", "in", "on", "from",
    "movies", "films", "shows", "similar", "like",
    "reviews", "review", "rating", "ratings", "summary", "summarize",
    "watch", "watching", "watchable", "tonight", "today",
}

# Quoted title e.g. like "Fight Club"
_QUOTED_RE = re.compile(r'"([^"]+)"')

_TRIGGER_PHRASES = [
    "similar to", "just like", "movies like", "films like",
    "in the style of", "reminds me of",
    "reviews of", "review of", "summarize", "summarise",
    "synopsis of", "plot of", "rating for", "about",
    "like",   # must come last (shortest, most general)
]


def _extract_seed_movies(query: str) -> list[str]:
    """Scan forward from a trigger phrase, collect words until a stop word."""
    # Quoted titles are exact — handle first
    quoted = _QUOTED_RE.findall(query)
    if quoted:
        return quoted[:3]

    words = query.split()
    q_lower = query.lower()
    seeds: list[str] = []

    for phrase in _TRIGGER_PHRASES:
        idx = q_lower.find(phrase)
        if idx == -1:
            continue

        # Find word index just after the trigger phrase
        after = query[idx + len(phrase):].lstrip()
        if not after:
            continue

        title_words: list[str] = []
        for word in after.split():
            clean = word.strip(".,!?\"'")
            if clean.lower() in _TITLE_STOP_WORDS:
                break
            title_words.append(clean)
            if len(title_words) == 5:   # max 5 words per title
                break

        title = " ".join(title_words).strip()
        if len(title) >= 2:
            seeds.append(title)

    return list(dict.fromkeys(seeds))[:3]


def _extract_genres(query: str) -> list[str]:
    found: list[str] = []
    q = _lower(query)
    for genre in _GENRES:
        if genre in q:
            found.append(genre)
    return found


def _extract_year_range(query: str) -> tuple[Optional[int], Optional[int]]:
    # "from 2000 to 2010"
    rng = re.search(r"from\s+(\d{4})\s+to\s+(\d{4})", query, re.IGNORECASE)
    if rng:
        return int(rng.group(1)), int(rng.group(2))
    # "2000s"
    decade = re.search(r"\b(19\d0|20[012]\d)s\b", query, re.IGNORECASE)
    if decade:
        y = int(decade.group(1))
        return y, y + 9
    # single year
    year = re.search(r"\b(19[5-9]\d|20[0-2]\d)\b", query)
    if year:
        y = int(year.group(1))
        return y, y
    return None, None


def _extract_country(query: str) -> Optional[str]:
    q = _lower(query)
    for word, code in _COUNTRY_MAP.items():
        if word in q:
            return code
    return None


def _extract_platforms(query: str) -> list[str]:
    known = ["netflix", "prime video", "amazon prime", "disney+", "disney plus",
             "hulu", "apple tv", "hbo max", "hbo", "peacock", "paramount+"]
    q = _lower(query)
    return [p for p in known if p in q]


# ── Main classifier ────────────────────────────────────────────────────────────

def classify_intent_sync(query: str, user_context: Optional[dict] = None) -> QueryIntent:
    q = _lower(query)

    # ── Entity extraction (runs for all intents) ──────────────────────────────
    seeds     = _extract_seed_movies(query)
    genres    = _extract_genres(query)
    country   = _extract_country(query)
    yr_from, yr_to = _extract_year_range(query)
    platforms = _extract_platforms(query)
    streaming_filter = bool(platforms) or _contains_any(q, {"streaming", "streamable", "watch online"})

    mood: Optional[str] = None
    for kw in ("funny", "scary", "dark", "intense", "feel-good", "emotional",
               "inspiring", "romantic", "action-packed", "thought-provoking"):
        if kw in q:
            mood = kw
            break

    entities = QueryEntities(
        seed_movies=seeds,
        genres=genres,
        country=country,
        year_from=yr_from,
        year_to=yr_to,
        streaming_filter=streaming_filter,
        platforms=platforms,
        mood=mood,
    )

    # ── Intent scoring ────────────────────────────────────────────────────────
    scores: dict[str, int] = {
        "find_similar":    3 if _contains_any(q, _SIMILAR_KWS) else 0,
        "recommend":       3 if _contains_any(q, _RECOMMEND_KWS) else 0,
        "summarize":       3 if _contains_any(q, _SUMMARIZE_KWS) else 0,
        "lookup":          3 if _contains_any(q, _LOOKUP_KWS) else 0,
        "discover":        3 if _contains_any(q, _DISCOVER_KWS) else 0,
        "mood_based":      3 if _contains_any(q, _MOOD_KWS) else 0,
        "filter_provider": 3 if _contains_any(q, _PROVIDER_KWS) else 0,
        "search":          0,
    }

    # Boost scores based on extracted entities
    if seeds:
        scores["find_similar"] += 2
        scores["summarize"]    += 1
        scores["lookup"]       += 1
    if genres:
        scores["discover"]  += 2
        scores["mood_based"] += 1
    if platforms or streaming_filter:
        scores["filter_provider"] += 2
    if user_context and user_context.get("user_id"):
        scores["recommend"] += 1

    # Search is a catch-all fallback
    has_meaningful_words = len(q.split()) >= 2
    if has_meaningful_words:
        scores["search"] = 1

    primary = max(scores, key=scores.__getitem__)
    # If no clear winner, fall back to discover or search
    if scores[primary] == 0:
        primary = "discover"

    # ── Derive flags ──────────────────────────────────────────────────────────
    requires_personalization = (
        primary == "recommend"
        or _contains_any(q, {"for me", "my taste", "personalised", "personalized", "i'd enjoy"})
    )
    requires_synthesis = primary in ("summarize", "lookup", "mood_based")

    complexity = "simple"
    active_tools = sum([
        bool(seeds), bool(genres), bool(platforms), requires_personalization
    ])
    if active_tools >= 2 or primary in ("find_similar", "filter_provider"):
        complexity = "medium"
    if active_tools >= 3 or primary in ("summarize",):
        complexity = "complex"

    # ── Human-readable interpretation ─────────────────────────────────────────
    interpreted_as = _build_interpretation(primary, entities, query)

    return QueryIntent(
        primary_intent=primary,
        entities=entities,
        requires_personalization=requires_personalization,
        requires_synthesis=requires_synthesis,
        complexity=complexity,
        interpreted_as=interpreted_as,
    )


def _build_interpretation(primary: str, entities: QueryEntities, raw: str) -> str:
    parts: list[str] = []

    if primary == "find_similar" and entities.seed_movies:
        parts.append(f"Movies similar to {entities.seed_movies[0]}")
    elif primary == "recommend":
        parts.append("Personalised recommendations")
    elif primary == "summarize" and entities.seed_movies:
        parts.append(f"Review summary for {entities.seed_movies[0]}")
    elif primary == "lookup" and entities.seed_movies:
        parts.append(f"Details about {entities.seed_movies[0]}")
    elif primary == "mood_based":
        mood_str = entities.mood or "matching your mood"
        parts.append(f"Movies that are {mood_str}")
    elif primary == "discover":
        parts.append("Trending & popular movies")
    elif primary == "filter_provider":
        if entities.platforms:
            parts.append(f"Movies available on {', '.join(entities.platforms)}")
        else:
            parts.append("Streamable movies")
    else:
        parts.append(f"Movies matching '{raw[:60]}'")

    if entities.genres:
        parts.append(f"genre: {', '.join(entities.genres)}")
    if entities.country:
        parts.append(f"in {entities.country}")
    if entities.year_from and entities.year_to:
        if entities.year_from == entities.year_to:
            parts.append(f"from {entities.year_from}")
        else:
            parts.append(f"{entities.year_from}–{entities.year_to}")

    return " — ".join(parts) if parts else raw[:80]


# ── Async wrapper (keeps app.py interface identical) ──────────────────────────

async def classify_intent(
    query: str,
    user_context: Optional[dict] = None,
) -> QueryIntent:
    return classify_intent_sync(query, user_context)
