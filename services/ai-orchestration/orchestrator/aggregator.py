"""
Aggregator — merges tool results into a ranked MovieResult list.

Steps:
  1. Collect every movie from every tool result into one candidate pool.
  2. Merge duplicate entries, keeping the best score.
  3. Score and rank with a composite formula.
  4. Fetch streaming providers for the top-N movies (parallel).
  5. If intent is filter_provider, keep only movies with providers.
  6. Optionally synthesise a natural-language summary.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

import litellm

from models.intent import QueryIntent
from models.query import MovieResult, Provider
from tools.providers_tool import fetch_providers

_MODEL = "groq/llama-3.3-70b-versatile"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_movies(value: Any) -> List[dict]:
    """Pull movie dicts out of whatever shape a tool returns."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("results", "recommendations", "movies"):
            if isinstance(value.get(key), list):
                return value[key]
        # Single movie object
        if value.get("movie_id") or value.get("id"):
            return [value]
    return []


def _score(movie: dict) -> float:
    vote_avg = float(movie.get("vote_average") or 0) / 10.0
    vote_cnt = float(movie.get("vote_count") or 0)
    popularity = float(movie.get("popularity") or 0)
    sim = float(movie.get("similarity_score") or movie.get("score") or 0)

    quality = (
        0.60 * vote_avg
        + 0.25 * min(vote_cnt / 500.0, 1.0)
        + 0.15 * min(popularity / 200.0, 1.0)
    )
    if sim > 0:
        return 0.55 * sim + 0.30 * quality + 0.15 * min(popularity / 200.0, 1.0)
    return 0.60 * quality + 0.40 * min(popularity / 200.0, 1.0)


def _build_movie_result(movie: dict, providers: List[dict]) -> Optional[MovieResult]:
    mid = movie.get("movie_id") or movie.get("id")
    if not mid:
        return None

    raw_date = str(movie.get("release_date") or "")
    year = int(raw_date[:4]) if len(raw_date) >= 4 and raw_date[:4].isdigit() else None

    genres = movie.get("genres") or []
    if genres and not isinstance(genres[0], str):
        genres = []

    return MovieResult(
        movie_id=int(mid),
        title=movie.get("title", "Unknown"),
        year=year,
        poster_path=movie.get("poster_path"),
        vote_average=round(float(movie.get("vote_average") or 0), 1),
        overview=(movie.get("overview") or "")[:300],
        genres=genres[:3],
        similarity_score=round(float(movie.get("similarity_score") or movie.get("score") or 0), 3) or None,
        explanation=movie.get("explanation"),
        providers=[
            Provider(name=p["name"], type=p["type"], logo=p.get("logo"))
            for p in providers[:3]
        ],
    )


async def _synthesise(
    results: List[MovieResult],
    original_query: str,
    interpreted_as: str,
) -> str:
    """LLM synthesis of movie results via litellm."""
    if not results:
        return f"No results found for: {original_query}"

    top_titles = ", ".join(
        f"{r.title} ({r.year})" if r.year else r.title
        for r in results[:5]
    )
    top = results[0]
    context = (
        f"User query: {original_query}\n"
        f"Interpreted as: {interpreted_as}\n"
        f"Total results: {len(results)}\n"
        f"Top matches: {top_titles}\n"
        f"Best pick overview: {top.overview[:200] if top.overview else 'N/A'}"
    )

    response = await litellm.acompletion(
        model=_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful movie assistant for CineScope. "
                    "Write a single concise sentence (max 40 words) that introduces the search results to the user. "
                    "Mention the top movie by name and briefly why it fits. No markdown, no lists, just prose."
                ),
            },
            {"role": "user", "content": context},
        ],
        max_tokens=80,
        temperature=0.4,
    )

    return response.choices[0].message.content.strip()


# ── Main entry point ───────────────────────────────────────────────────────────

async def aggregate(
    tool_results: Dict[str, Any],
    intent: QueryIntent,
    original_query: str,
    max_results: int = 10,
    include_synthesis: bool = False,
    locale: str = "US",
) -> Tuple[List[MovieResult], Optional[str]]:
    # ── 1. Collect candidates ─────────────────────────────────────────────────
    candidates: Dict[int, dict] = {}

    for node_id, value in tool_results.items():
        if node_id.startswith("_"):
            continue
        for movie in _extract_movies(value):
            mid = movie.get("movie_id") or movie.get("id")
            if not mid:
                continue
            mid = int(mid)
            if mid not in candidates:
                candidates[mid] = dict(movie)
                candidates[mid]["movie_id"] = mid
            else:
                # Keep best score
                existing = candidates[mid]
                new_sim = float(movie.get("similarity_score") or movie.get("score") or 0)
                old_sim = float(existing.get("similarity_score") or existing.get("score") or 0)
                if new_sim > old_sim:
                    existing["similarity_score"] = new_sim
                # Merge genre names if missing
                if not existing.get("genres") and movie.get("genres"):
                    existing["genres"] = movie["genres"]

    if not candidates:
        return [], None

    # ── 2. Rank ───────────────────────────────────────────────────────────────
    ranked = sorted(candidates.values(), key=_score, reverse=True)

    # For filter_provider we need a bigger pool before the provider filter below
    pool_size = max_results * 5 if intent.primary_intent == "filter_provider" else max_results * 2
    pool = ranked[:pool_size]

    # ── 3. Fetch providers for the pool ──────────────────────────────────────
    movie_ids = [int(m.get("movie_id") or m.get("id")) for m in pool]
    country = intent.entities.country or locale

    if intent.options.include_providers if hasattr(intent, "options") else True:
        provider_map = await fetch_providers(movie_ids, country=country)
    else:
        provider_map = {}

    # ── 4. Filter by provider if requested ────────────────────────────────────
    if intent.primary_intent == "filter_provider":
        pool = [m for m in pool if provider_map.get(int(m.get("movie_id") or m.get("id")), [])]

    # ── 5. Build final MovieResult list ───────────────────────────────────────
    results: List[MovieResult] = []
    for movie in pool:
        mid = int(movie.get("movie_id") or movie.get("id"))
        mr = _build_movie_result(movie, provider_map.get(mid, []))
        if mr:
            results.append(mr)
        if len(results) >= max_results:
            break

    # ── 6. Synthesise ─────────────────────────────────────────────────────────
    synthesis: Optional[str] = None
    if intent.primary_intent in ("summarize", "lookup"):
        reviews_data = tool_results.get("reviews")
        details_data = tool_results.get("movie_details")
        synthesis = await _synthesise_review(reviews_data, details_data, original_query)
    elif include_synthesis and results:
        synthesis = await _synthesise(results, original_query, intent.interpreted_as)

    return results, synthesis


async def _synthesise_review(
    reviews_data: Optional[dict],
    details_data: Optional[dict],
    query: str,
) -> Optional[str]:
    """LLM synthesis for review/lookup intents via litellm."""
    if not details_data and not reviews_data:
        return None

    context_parts: list[str] = [f"User query: {query}"]

    if details_data:
        title = details_data.get("title", "")
        year = str(details_data.get("release_date", ""))[:4]
        tagline = details_data.get("tagline", "")
        overview = (details_data.get("overview") or "")[:300]
        runtime = details_data.get("runtime")
        cast = details_data.get("cast", [])

        context_parts.append(f"Movie: {title} ({year})")
        if tagline:
            context_parts.append(f"Tagline: {tagline}")
        if overview:
            context_parts.append(f"Overview: {overview}")
        if runtime:
            context_parts.append(f"Runtime: {runtime} min")
        if cast:
            context_parts.append(f"Cast: {', '.join(cast[:4])}")

    if reviews_data:
        reviews = reviews_data.get("reviews", [])[:3]
        rated = [r["rating"] for r in reviews if r.get("rating")]
        if rated:
            avg = round(sum(rated) / len(rated), 1)
            context_parts.append(f"Average user rating: {avg}/10")
        for r in reviews:
            excerpt = (r.get("content") or "")[:200]
            if excerpt:
                context_parts.append(f'Review by {r.get("author", "user")}: "{excerpt}"')

    response = await litellm.acompletion(
        model=_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful movie assistant for CineScope. "
                    "Using the provided movie details and reviews, write a concise 2-3 sentence summary "
                    "that answers the user's query. Include the rating if available. "
                    "No markdown, no bullet points, just clear prose."
                ),
            },
            {"role": "user", "content": "\n".join(context_parts)},
        ],
        max_tokens=150,
        temperature=0.4,
    )

    return response.choices[0].message.content.strip()
