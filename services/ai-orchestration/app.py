"""
CineScope AI Orchestration Layer
POST /api/query  — single intelligent endpoint

Pipeline per request:
  semantic cache → intent classification (Claude Haiku) →
  tool planning → parallel execution (asyncio DAG) →
  aggregation + provider fetch → optional synthesis (Claude Sonnet) →
  cache write → response
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from cache.semantic_cache import cache_get, cache_set, make_query_key
from models.query import QueryMeta, QueryRequest, QueryResponse
from orchestrator.aggregator import aggregate
from orchestrator.circuit_breaker import all_states
from orchestrator.execution_engine import ExecutionEngine
from orchestrator.intent_classifier import classify_intent
from orchestrator.tool_planner import build_plan

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


# ── /api/query ────────────────────────────────────────────────────────────────

@app.post("/api/query", response_model=QueryResponse)
async def query_endpoint(
    request: QueryRequest,
    authorization: Optional[str] = Header(None),
):
    query_id = f"q_{uuid.uuid4().hex[:10]}"
    t_start = time.monotonic()

    # ── Cache lookup ──────────────────────────────────────────────────────────
    user_segment = "auth" if authorization else "anon"
    cache_key = make_query_key(request.q, request.locale, user_segment)

    cached = await cache_get(cache_key)
    if cached:
        cached["query_id"] = query_id
        cached.setdefault("meta", {})["cache_hit"] = True
        cached["meta"].setdefault("cache_tier", "L1/L2")
        return QueryResponse(**cached)

    # ── Intent classification ─────────────────────────────────────────────────
    user_ctx: dict = {}
    if request.context:
        user_ctx = request.context.model_dump(exclude_none=True)
    if request.userId:
        user_ctx["user_id"] = request.userId

    intent = await classify_intent(request.q, user_ctx or None)

    # ── Tool planning ─────────────────────────────────────────────────────────
    plan = build_plan(
        intent=intent,
        user_id=request.userId,
        locale=request.locale,
        max_results=request.options.max_results,
    )

    # ── Parallel execution ────────────────────────────────────────────────────
    tool_results = await _engine.run(plan)

    # ── Aggregation + providers + synthesis ───────────────────────────────────
    results, synthesis = await aggregate(
        tool_results=tool_results,
        intent=intent,
        original_query=request.q,
        max_results=request.options.max_results,
        include_synthesis=request.options.include_synthesis or intent.requires_synthesis,
        locale=request.locale,
    )

    elapsed_ms = int((time.monotonic() - t_start) * 1_000)
    services_invoked: list = tool_results.get("_services_invoked", [])

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
        ),
    )

    # Write-through cache (skip personalized results)
    if not intent.requires_personalization:
        await cache_set(cache_key, response.model_dump(), ttl=300)

    return response


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
