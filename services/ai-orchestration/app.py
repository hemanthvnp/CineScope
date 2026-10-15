"""
CineScope AI Orchestration Layer
POST /api/query         — single intelligent endpoint
POST /api/query/stream  — the same pipeline, streamed as Server-Sent Events

Pipeline per request:
  query cache → [speculative TMDB prefetch ∥ intent classification (Groq via litellm)] →
  tool planning → intent cache → parallel execution (asyncio DAG) →
  aggregation → [provider fetch ∥ optional synthesis (Groq via litellm)] →
  cache write → response

Conversations: every response carries a `conversation` state; sending it back with the next
message ("only on Netflix", "something newer", "show me more") refines that search.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, List, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from cache.semantic_cache import (
    cache_get, cache_set, canonical_params, make_intent_key, make_query_key, normalise_query,
)
from models.intent import ExecutionPlan, QueryIntent
from models.query import MAX_SHOWN_IDS, ConversationState, QueryMeta, QueryRequest, QueryResponse
from orchestrator.aggregator import aggregate_stream
from orchestrator.circuit_breaker import all_states
from orchestrator.execution_engine import ExecutionEngine
from orchestrator.intent_classifier import apply_filters, classify_intent, filter_only_intent
from orchestrator.speculator import guess_plan
from orchestrator.tool_planner import build_plan
from tools.tmdb_tool import genre_ids

_engine = ExecutionEngine()


# ── Startup / Shutdown ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    async def _warm_semantic_index():
        try:
            from tools.semantic_search_tool import _ensure_initialized
            await _ensure_initialized()
        except Exception as exc:
            print(f"[orchestration] Semantic index warm-up error: {exc}")

    asyncio.create_task(_warm_semantic_index())
    yield
    print("[orchestration] Shutting down")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="CineScope AI Orchestration Layer",
    description=(
        "Single intelligent endpoint — POST /api/query with natural language. "
        "The AI layer classifies intent, plans tool calls, executes in parallel, "
        "aggregates results, and optionally synthesises a response."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _watched_ids(tool_results: dict) -> set:
    """Movies the user has already watched/rated — don't recommend them again."""
    profile = tool_results.get("user_data") or {}
    return {int(i) for i in profile.get("watched_ids", []) if i is not None}


def _intent_cache_key(
    plan: ExecutionPlan, intent: QueryIntent, request: QueryRequest, user_segment: str, synthesis: bool,
) -> str:
    """Everything that decides the response, minus the wording of the query.

    The plan's params fix what every tool returns; the entities and options fix how the
    aggregator filters and ranks them. So "90s sci-fi" and "science fiction movies from
    the 1990s" share an entry once the LLM resolves both to the same plan.
    """
    e = intent.entities
    signature = {
        "intent": intent.primary_intent,
        "plan": [[n.id, n.tool, canonical_params(n.params)] for n in sorted(plan.nodes, key=lambda n: n.id)],
        "genres": sorted(set(genre_ids(e.genres))),
        "language": (e.language or "").lower(),
        "years": [e.year_from, e.year_to],
        "min_rating": float(e.min_rating) if e.min_rating is not None else None,
        "hard_filters": e.hard_filters,
        "platforms": sorted(p.lower() for p in e.platforms) if e.explicit_platforms else [],
        "country": e.country or request.locale,
        "user": user_segment,
        "options": request.options.model_dump(),
        # A synthesis answers the user's exact words, so only identical queries may share it
        "query": normalise_query(request.q) if synthesis else None,
    }
    return make_intent_key(signature)


def _next_conversation(request: QueryRequest, intent: QueryIntent, result_ids: List[int]) -> ConversationState:
    """The state the client sends back to ask a follow-up to this response."""
    previous = request.conversation
    refined = bool(previous and intent.refines_previous)
    shown = (previous.shown_ids if refined else []) + list(result_ids)
    shown = list(dict.fromkeys(shown))[-MAX_SHOWN_IDS:]     # dedupe, keep the most recent
    return ConversationState(
        query=request.q[:500],
        intent=intent.primary_intent,
        interpreted_as=intent.interpreted_as[:500],
        entities=intent.entities,
        shown_ids=shown,
        turn=previous.turn + 1 if refined else 1,
    )


# ── /api/query ────────────────────────────────────────────────────────────────

async def _run_query(request: QueryRequest, authorization: Optional[str]) -> AsyncIterator[Tuple[str, Any]]:
    """The query pipeline as a sequence of events, each emitted as soon as it is known:

      intent     what the query was understood as (right after the LLM call)
      preview    ranked results, before streaming providers are fetched
      results    the final results
      synthesis  the LLM summary, when there is one
      done       the complete QueryResponse (the only event on a cache hit)

    /api/query returns the `done` payload; /api/query/stream sends every event.
    """
    query_id = f"q_{uuid.uuid4().hex[:10]}"
    t_start = time.monotonic()
    previous = request.conversation

    # ── Cache lookup ──────────────────────────────────────────────────────────
    user_segment = "auth" if authorization else "anon"
    active_filters = request.filters if request.filters and request.filters.is_active() else None
    key_parts = active_filters.model_dump(exclude_none=True) if active_filters else None
    if previous:
        # "only on Netflix" means something different after every previous search
        key_parts = {**(key_parts or {}), "_conversation": previous.model_dump()}
    cache_key = make_query_key(request.q, request.locale, user_segment, key_parts)

    cached = await cache_get(cache_key)
    if cached:
        cached["query_id"] = query_id
        cached.setdefault("meta", {})["cache_hit"] = True
        cached["meta"]["cache_tier"] = "query"
        yield "done", QueryResponse(**cached)
        return

    # ── Speculative prefetch ──────────────────────────────────────────────────
    # Start the TMDB calls a rule-based parse predicts so they overlap with the LLM call.
    # Not for follow-ups: "only on netflix" alone predicts nothing about the search it refines.
    if request.q.strip() and not previous:
        _engine.prefetch(guess_plan(request.q, active_filters, request.options.max_results))

    # ── Intent classification ─────────────────────────────────────────────────
    user_ctx: dict = {}
    if request.context:
        user_ctx = request.context.model_dump(exclude_none=True)
    if request.userId:
        user_ctx["user_id"] = request.userId

    if request.q.strip():
        intent = await classify_intent(request.q, user_ctx or None, previous)
    else:
        intent = filter_only_intent(active_filters)   # filters alone — no LLM call needed
    intent = apply_filters(intent, active_filters)    # explicit filters override LLM-inferred ones
    if request.context and request.context.mood and not intent.entities.mood:
        intent.entities.mood = request.context.mood

    yield "intent", {
        "query_id": query_id,
        "intent": intent.primary_intent,
        "interpreted_as": intent.interpreted_as,
        "refines_previous": intent.refines_previous,
        "degraded": intent.degraded,
    }

    # ── Tool planning ─────────────────────────────────────────────────────────
    # "Show me more": leave out what this conversation already showed, and fetch enough to replace it
    shown = set(previous.shown_ids) if previous and intent.exclude_shown else set()
    plan = build_plan(
        intent=intent,
        user_id=request.userId,
        locale=request.locale,
        max_results=min(request.options.max_results + len(shown), 50),
    )
    include_synthesis = request.options.include_synthesis or intent.requires_synthesis

    # ── Intent cache: same meaning, different wording ─────────────────────────
    intent_key = None
    if not intent.requires_personalization and not shown:
        intent_key = _intent_cache_key(plan, intent, request, user_segment, include_synthesis)
        cached = await cache_get(intent_key)
        if cached:
            hit = {**cached, "query_id": query_id, "interpreted_as": intent.interpreted_as}
            hit["meta"] = {
                **cached.get("meta", {}),
                "cache_hit": True,
                "cache_tier": "intent",
                "interpreted_as": intent.interpreted_as,
                "execution_ms": int((time.monotonic() - t_start) * 1_000),
            }
            # The cached response may come from another conversation (or none): this one continues from here
            hit["conversation"] = _next_conversation(
                request, intent, [r["movie_id"] for r in cached.get("results", [])],
            ).model_dump()
            await cache_set(cache_key, hit, ttl=300)   # an exact repeat of this wording now skips the LLM too
            yield "done", QueryResponse(**hit)
            return

    # ── Parallel execution ────────────────────────────────────────────────────
    tool_results = await _engine.run(plan)

    # ── Aggregation + providers + synthesis ───────────────────────────────────
    exclude_ids = shown | (_watched_ids(tool_results) if intent.requires_personalization else set())
    results: list = []
    synthesis: Optional[str] = None
    async for stage, value in aggregate_stream(
        tool_results=tool_results,
        intent=intent,
        original_query=request.q or intent.interpreted_as,
        max_results=request.options.max_results,
        include_synthesis=include_synthesis,
        locale=request.locale,
        include_providers=request.options.include_providers,
        exclude_ids=exclude_ids or None,
    ):
        if stage == "synthesis":
            synthesis = value
            if value:
                yield "synthesis", {"synthesis": value}
        else:
            if stage == "results":
                results = value
            yield stage, {"results": value}

    elapsed_ms = int((time.monotonic() - t_start) * 1_000)
    services_invoked: list = tool_results.get("_services_invoked", [])
    # Rule-based intent, or a synthesis that should exist but failed (aggregator returns None then)
    degraded = intent.degraded or bool(include_synthesis and results and synthesis is None)

    response = QueryResponse(
        query_id=query_id,
        intent=intent.primary_intent,
        interpreted_as=intent.interpreted_as,
        synthesis=synthesis,
        results=results,
        meta=QueryMeta(
            total_results=len(results),
            services_invoked=services_invoked,
            execution_ms=elapsed_ms,
            cache_hit=False,
            personalized=intent.requires_personalization and request.userId is not None,
            intent=intent.primary_intent,
            interpreted_as=intent.interpreted_as,
            degraded=degraded,
        ),
        conversation=_next_conversation(request, intent, [r.movie_id for r in results]),
    )

    # Write-through cache under both keys (skip personalized results, and degraded ones so
    # the full answer is computed again as soon as the LLM is back)
    if intent_key and not degraded:
        payload = response.model_dump()
        await cache_set(cache_key, payload, ttl=300)
        await cache_set(intent_key, payload, ttl=300)

    yield "done", response


@app.post("/api/query", response_model=QueryResponse)
async def query_endpoint(
    request: QueryRequest,
    authorization: Optional[str] = Header(None),
):
    async for event, data in _run_query(request, authorization):
        if event == "done":
            return data
    raise HTTPException(status_code=500, detail="Query pipeline ended without a response")


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(jsonable_encoder(data))}\n\n"


@app.post("/api/query/stream")
async def query_stream_endpoint(
    request: QueryRequest,
    authorization: Optional[str] = Header(None),
):
    """/api/query as Server-Sent Events: the interpretation, results, providers and synthesis
    each arrive as soon as they're ready instead of all at once at the end."""
    async def events():
        try:
            async for event, data in _run_query(request, authorization):
                yield _sse(event, data)
        except Exception as exc:
            print(f"[orchestration] Streamed query failed: {str(exc)[:200]}")
            yield _sse("error", {"error": "Failed to process query"})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        # X-Accel-Buffering: nginx (the frontend's proxy) would otherwise hold events back
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Supporting endpoints ──────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "service": "ai-orchestration",
        "status": "healthy",
        "version": "1.0.0",
        "circuit_breakers": all_states(),
    }


class ClassifyRequest(BaseModel):
    q: str = Field(..., min_length=1)


@app.post("/debug/classify")
async def debug_classify(req: ClassifyRequest):
    """Inspect how a query is classified (dev/debug only)."""
    intent = await classify_intent(req.q)
    return intent.model_dump()


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "9000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
