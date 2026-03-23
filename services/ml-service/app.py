"""
CineScope ML Recommendation Service

A FastAPI microservice that provides hybrid movie recommendations
combining content-based (TF-IDF) and collaborative (SVD) filtering.

Endpoints:
  POST /recommend  — Get personalized recommendations for a user
  GET  /health     — Service health check
  POST /refresh    — Rebuild ML models from latest data

Architecture:
  This service reads from the same MongoDB as the Node.js
  recommendation-service. It handles all ML/AI computation and
  returns enriched recommendations with explanations.
"""

import os
import traceback
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from recommender.hybrid import initialize_models, get_hybrid_recommendations


# ---------------------------------------------------------------------------
# Pydantic models for request/response validation
# ---------------------------------------------------------------------------

class RecommendRequest(BaseModel):
    userId: str = Field(..., description="MongoDB ObjectId of the user")
    limit: Optional[int] = Field(20, ge=1, le=100, description="Max recommendations")


class HealthResponse(BaseModel):
    service: str = "ml-recommendation-service"
    status: str = "healthy"
    version: str = "1.0.0"


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    On startup: connect to MongoDB and build ML models.
    This runs the heavy TF-IDF and SVD computations once.
    """
    try:
        initialize_models()
        print("[ml-service] Ready to serve recommendations")
    except Exception as e:
        print(f"[ml-service] WARNING: Model initialization failed: {e}")
        print("[ml-service] Service will start but recommendations may be limited")
        traceback.print_exc()
    yield
    print("[ml-service] Shutting down")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CineScope ML Recommendation Service",
    description="Hybrid recommendation engine with TF-IDF and SVD",
    version="1.0.0",
    lifespan=lifespan
)

# CORS — allow all origins in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Service health check endpoint."""
    return HealthResponse()


@app.post("/recommend")
async def recommend(request: RecommendRequest):
    """
    Get personalized movie recommendations for a user.

    The engine selects the best strategy based on available user data:
    - **hybrid**: Full TF-IDF + SVD combination (enough ratings)
    - **content_only**: TF-IDF only (some ratings, not enough for SVD)
    - **genre_fallback**: Genre preference scoring (no ratings, has preferences)
    - **trending_fallback**: Popular movies (no user data at all)

    Each recommendation includes an explanation for transparency.
    """
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
async def refresh_models():
    """
    Rebuild ML models from latest database data.
    Call this after significant new ratings or data changes.
    """
    try:
        initialize_models()
        return {"status": "success", "message": "Models refreshed successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh models: {str(e)}"
        )


# ---------------------------------------------------------------------------
# Run with: python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
