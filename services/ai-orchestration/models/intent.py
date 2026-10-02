from __future__ import annotations
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel


class QueryEntities(BaseModel):
    seed_movies: List[str] = []
    genres: List[str] = []
    country: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    streaming_filter: bool = False
    platforms: List[str] = []
    mood: Optional[str] = None
    director: Optional[str] = None
    actor: Optional[str] = None
    language: Optional[str] = None
    min_rating: Optional[float] = None
    # True when genre/language/year/rating must be enforced on results (explicit filters, or extracted from the query)
    hard_filters: bool = False
    # True only for explicit `platforms` filters: LLM-extracted names ("Disney+") are too fuzzy to match on
    explicit_platforms: bool = False


class QueryIntent(BaseModel):
    primary_intent: Literal[
        "discover", "find_similar", "recommend", "search",
        "filter_provider", "summarize", "mood_based", "lookup"
    ]
    entities: QueryEntities = QueryEntities()
    requires_personalization: bool = False
    requires_synthesis: bool = False
    complexity: Literal["simple", "medium", "complex"] = "medium"
    interpreted_as: str = ""


class PlanNode(BaseModel):
    id: str
    tool: str
    params: Dict[str, Any] = {}
    dependencies: List[str] = []
    optional: bool = False


class ExecutionPlan(BaseModel):
    nodes: List[PlanNode]
    merge_strategy: str = "default"
