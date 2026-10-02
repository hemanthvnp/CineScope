from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator


class QueryOptions(BaseModel):
    max_results: int = Field(default=10, ge=1, le=50)
    include_providers: bool = True
    include_synthesis: bool = False


class QueryContext(BaseModel):
    mood: Optional[str] = None


ERA_RANGES = {
    "classic": (1900, 1979),
    "old": (1980, 1999),
    "modern": (2000, 2015),
    "recent": (2016, 2099),
}


class QueryFilters(BaseModel):
    """Structured filters. Any single one, or any combination, may be sent with (or without) `q`."""
    genres: List[str] = Field(default_factory=list, description="Genre names or TMDB genre ids")
    language: Optional[str] = Field(default=None, description="Original language, ISO 639-1 (e.g. 'hi')")
    year: Optional[int] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    era: Optional[str] = Field(default=None, description="Classic | Old | Modern | Recent")
    min_rating: Optional[float] = Field(default=None, ge=0, le=10)
    platforms: List[str] = Field(default_factory=list)
    country: Optional[str] = None

    def year_range(self) -> tuple[Optional[int], Optional[int]]:
        """Resolve year / year_from / year_to / era into one (from, to) range."""
        lo, hi = self.year_from, self.year_to
        if self.year:
            lo, hi = self.year, self.year
        elif self.era and self.era.lower() in ERA_RANGES:
            era_lo, era_hi = ERA_RANGES[self.era.lower()]
            lo = max(lo, era_lo) if lo else era_lo
            hi = min(hi, era_hi) if hi else era_hi
        return lo, hi

    def is_active(self) -> bool:
        return bool(
            self.genres or self.language or self.min_rating is not None
            or self.platforms or any(self.year_range())
        )


class QueryRequest(BaseModel):
    q: str = Field(default="", max_length=500, description="Natural language movie query (optional if filters given)")
    userId: Optional[str] = None
    locale: str = Field(default="US", description="ISO 3166-1 alpha-2 country code")
    context: Optional[QueryContext] = None
    filters: Optional[QueryFilters] = None
    options: QueryOptions = QueryOptions()

    @model_validator(mode="after")
    def _need_query_or_filters(self):
        if not self.q.strip() and not (self.filters and self.filters.is_active()):
            raise ValueError("Provide a query `q` or at least one filter")
        return self


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
