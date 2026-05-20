"""
Aggregator — merges tool results into a ranked MovieResult list.

Steps:
  1. Collect every movie from every tool result into one candidate pool.
  2. Merge duplicate entries, keeping the best score.
  3. Score and rank with a composite formula.
  4. Fetch streaming providers for the top-N movies (parallel).
  5. If intent is filter_provider, keep only movies with providers.
  6. Optionally synthesise a short intro with Claude Sonnet.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from models.intent import QueryIntent
from models.query import MovieResult, Provider
from tools.providers_tool import fetch_providers


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


def _synthesise(
    results: List[MovieResult],
    original_query: str,
    interpreted_as: str,
) -> str:
    """Template-based synthesis — free, zero latency."""
    count = len(results)
    if not count:
        return f"No results found for: {original_query}"

    top = results[0]
    genres_str = ", ".join(top.genres[:2]) if top.genres else ""
    genre_note = f" across {genres_str}" if genres_str else ""

    return (
        f"Found {count} movie{'s' if count != 1 else ''}{genre_note} "
        f"matching \"{interpreted_as}\". "
        f"Top pick: {top.title}"
        f"{f' ({top.year})' if top.year else ''}"
        f"{f' — {top.overview[:120]}…' if top.overview else '.'}"
    )


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
        synthesis = _synthesise_review(reviews_data, details_data, original_query)
    elif include_synthesis and results:
        synthesis = _synthesise(results, original_query, intent.interpreted_as)

    return results, synthesis


def _synthesise_review(
    reviews_data: Optional[dict],
    details_data: Optional[dict],
    query: str,
) -> Optional[str]:
    """Template-based review/lookup synthesis — free, zero latency."""
    parts: List[str] = []

    if details_data:
        title = details_data.get("title", "")
        year  = str(details_data.get("release_date", ""))[:4]
        tagline = details_data.get("tagline", "")
        overview = (details_data.get("overview") or "")[:250]
        runtime = details_data.get("runtime")
        cast = details_data.get("cast", [])

        header = f"{title} ({year})" if year else title
        if tagline:
            header += f' — "{tagline}"'
        parts.append(header)
        if overview:
            parts.append(overview)
        if runtime:
            parts.append(f"Runtime: {runtime} min")
        if cast:
            parts.append(f"Starring: {', '.join(cast[:4])}")

    if reviews_data:
        reviews = reviews_data.get("reviews", [])[:3]
        if reviews:
            avg_rating = None
            rated = [r["rating"] for r in reviews if r.get("rating")]
            if rated:
                avg_rating = round(sum(rated) / len(rated), 1)

            parts.append(
                f"Community rating: {avg_rating}/10" if avg_rating
                else f"{reviews_data.get('total_reviews', len(reviews))} reviews"
            )
            excerpt = reviews[0].get("content", "")[:200]
            if excerpt:
                author = reviews[0].get("author", "Reviewer")
                parts.append(f'"{excerpt}…" — {author}')

    return " | ".join(parts) if parts else None
