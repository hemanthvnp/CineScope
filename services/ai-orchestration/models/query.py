from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class QueryOptions(BaseModel):
    max_results: int = Field(default=10, ge=1, le=50)
    include_providers: bool = True
    include_synthesis: bool = False


class QueryContext(BaseModel):
    last_movie_viewed: Optional[int] = None
    mood: Optional[str] = None


class QueryRequest(BaseModel):
    q: str = Field(..., min_length=1, max_length=500, description="Natural language movie query")
    userId: Optional[str] = None
    locale: str = Field(default="US", description="ISO 3166-1 alpha-2 country code")
    context: Optional[QueryContext] = None
    options: QueryOptions = QueryOptions()


class Provider(BaseModel):
    name: str
    type: str                   # flatrate | rent | buy
    logo: Optional[str] = None


class MovieResult(BaseModel):
    movie_id: int
    title: str
    year: Optional[int] = None
    poster_path: Optional[str] = None
    vote_average: float = 0.0
    overview: str = ""
    genres: List[str] = []
    similarity_score: Optional[float] = None
    explanation: Optional[str] = None
    providers: List[Provider] = []


class QueryMeta(BaseModel):
    total_results: int
    services_invoked: List[str]
    execution_ms: int
    cache_hit: bool
    cache_tier: Optional[str] = None
    personalized: bool
    intent: str
    interpreted_as: str


class QueryResponse(BaseModel):
    query_id: str
    intent: str
    interpreted_as: str
    synthesis: Optional[str] = None
    results: List[MovieResult]
    meta: QueryMeta
