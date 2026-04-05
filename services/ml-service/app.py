

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




class RecommendRequest(BaseModel):
    userId: str = Field(..., description="MongoDB ObjectId of the user")
    limit: Optional[int] = Field(20, ge=1, le=100, description="Max recommendations")


class HealthResponse(BaseModel):
    service: str = "ml-recommendation-service"
    status: str = "healthy"
    version: str = "1.0.0"




@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    
    async def _init_task():
        try:
            print("[ml-service] Starting background model initialization...")
            initialize_models()
            print("[ml-service] Model initialization complete. Ready to serve recommendations.")
        except Exception as e:
            print(f"[ml-service] WARNING: Background model initialization failed: {e}")
            traceback.print_exc()

    init_task = asyncio.create_task(_init_task())
    
    yield
    print("[ml-service] Shutting down")
    init_task.cancel()




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




@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse()


@app.post("/recommend")
async def recommend(request: RecommendRequest):
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
    try:
        initialize_models()
        return {"status": "success", "message": "Models refreshed successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh models: {str(e)}"
        )



if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
