import os
import traceback
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from events import create_consumer
from recommender import hybrid
from recommender.hybrid import get_hybrid_recommendations, install_models, prepare_models
from refresher import ModelRefresher

refresher = ModelRefresher(
    prepare_models, install_models,
    debounce_s=float(os.getenv("REFRESH_DEBOUNCE_S", "2")),
)
consumer = create_consumer(refresher)


class RecommendRequest(BaseModel):
    userId: str = Field(..., description="MongoDB ObjectId of the user")
    limit: Optional[int] = Field(20, ge=1, le=100, description="Max recommendations")


class MetricsRequest(BaseModel):
    k_values: Optional[list] = Field(
        default=[5, 10, 20],
        description="List of K values for top-K metrics"
    )
    min_ratings: Optional[int] = Field(
        default=5, ge=2, le=50,
        description="Minimum ratings a user must have to be included"
    )
    max_users: Optional[int] = Field(
        default=100, ge=1, le=500,
        description="Maximum number of users to evaluate"
    )


class HealthResponse(BaseModel):
    service: str = "ml-recommendation-service"
    status: str = "healthy"
    version: str = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    tasks = [asyncio.create_task(refresher.run())]
    if consumer:
        tasks.append(asyncio.create_task(consumer.run()))
        print("[ml-service] Consuming rating events from Redis")
    else:
        print("[ml-service] REDIS_URL not set: models refresh via POST /refresh only")
    # Initial build, in the background so the service starts at once
    app.state.initial_build = refresher.request()

    yield
    print("[ml-service] Shutting down")
    for task in tasks:
        task.cancel()


app = FastAPI(
    title="CineScope ML Recommendation Service",
    description="Hybrid recommendation engine with TF-IDF and SVD",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.api_route("/health", methods=["GET", "HEAD"], response_model=HealthResponse)
async def health_check():
    return HealthResponse()


@app.post("/recommend")
async def recommend(request: RecommendRequest):
    if not hybrid._models_initialized:
        # Cold start: wait for the background build rather than let get_hybrid_recommendations
        # build the models a second time, inline, blocking the event loop while it runs
        try:
            await refresher.wait_for(app.state.initial_build)
        except Exception:
            pass    # that build failed: get_hybrid_recommendations retries it inline
    try:
        result = get_hybrid_recommendations(
            user_id=request.userId,
            limit=request.limit
        )
        return result

    except Exception as e:
        print(f"[ml-service] Error generating recommendations: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate recommendations: {str(e)}"
        )


@app.post("/refresh")
async def refresh_models(wait: bool = Query(False, description="Return only once the rebuild has finished")):
    """Fallback path when the gateway can't publish rating events. Concurrent calls share one rebuild."""
    if not wait:
        refresher.request()
        return {"status": "scheduled"}
    try:
        await refresher.refresh()
        return {"status": "success", "message": "Models refreshed successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh models: {str(e)}"
        )


@app.get("/pipeline")
async def pipeline_stats():
    """How model refreshes are being triggered, and how many rebuilds the coalescing saved."""
    return {
        "mode": "redis-stream" if consumer else "http",
        "refresher": refresher.stats,
        "consumer": consumer.stats if consumer else None,
    }


@app.post("/metrics")
async def offline_metrics(request: MetricsRequest):
    """
    Leave-one-out offline evaluation.

    For each user with at least `min_ratings` ratings, holds out their
    highest-rated movie and checks whether the content-based recommender
    recovers it in the top-K results.

    Returns Hit Rate@K, Precision@K, Recall@K, MRR, NDCG@K, and
    catalog coverage across all evaluated users.
    """
    try:
        from recommender.evaluator import evaluate
        result = evaluate(
            k_values=request.k_values,
            min_ratings=request.min_ratings,
            max_users=request.max_users,
        )
        return result
    except Exception as e:
        print(f"[ml-service] Error running offline evaluation: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
