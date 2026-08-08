from typing import Dict, List, Optional, Union, Any
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class CategoryDetails(BaseModel):
    """Category relation details if joined."""
    id: Optional[Union[str, UUID]] = None
    name: Optional[str] = None
    description: Optional[str] = None


class DishRecommendation(BaseModel):
    """
    Individual dish recommendation model containing menu metadata matching your menu database schema.
    """

    id: Union[int, str, UUID] = Field(..., description="Unique dish identifier (UUID string or int)")
    name: str = Field(..., description="Name of the menu item")
    description: str = Field(..., description="Culinary description of the dish")
    price: float = Field(..., description="Price of the dish as float")
    image: Optional[str] = Field(None, description="Image URL of the dish")
    image_url: Optional[str] = Field(None, description="Alias image URL for backward compatibility")
    category: Optional[Union[str, CategoryDetails]] = Field(
        None, description="Category name or Category object"
    )
    categoryId: Optional[Union[str, UUID]] = Field(None, description="Associated Category UUID")
    available: bool = Field(default=True, description="Availability flag")
    featured: bool = Field(default=False, description="Featured dish flag")
    discount: float = Field(default=0.0, description="Discount amount")
    popularity: int = Field(default=0, description="Popularity index score")
    is_vegetarian: bool = Field(default=True, description="Dietary flag for vegetarian dish")
    match_score: float = Field(
        ...,
        description="Calculated similarity match score between 0.0 and 1.0 (higher is better)",
    )
    distance: float = Field(
        ...,
        description="Raw pgvector Euclidean L2 distance (<->) vector score",
    )

    @field_validator("id", "categoryId", mode="before")
    @classmethod
    def format_id_to_str_if_uuid(cls, v: Any) -> Any:
        if isinstance(v, UUID):
            return str(v)
        return v

    @field_validator("price", "discount", mode="before")
    @classmethod
    def parse_float_from_str(cls, v: Any) -> float:
        if v is None:
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        try:
            return float(str(v))
        except (ValueError, TypeError):
            return 0.0


class RecommendationFiltersApplied(BaseModel):
    """Echo of active pre-filters applied to the recommendation query."""

    max_price: Optional[float] = None
    category: Optional[str] = None


class RecommendationResponse(BaseModel):
    """
    Top-level API response structure returned by POST /api/v1/recommend.
    """

    status: str = Field(default="success", description="Response status message")
    query_craving: str = Field(..., description="Original user craving query echo")
    filters_applied: RecommendationFiltersApplied = Field(
        ..., description="Summary of applied database pre-filters"
    )
    total_matches: int = Field(..., description="Number of recommendations returned")
    recommendations: List[DishRecommendation] = Field(
        ..., description="List of top matching dish recommendations"
    )
    cached: bool = Field(
        default=False, description="Flag indicating if response was served from Upstash Redis cache"
    )


class HealthCheckResponse(BaseModel):
    """
    System health & readiness check endpoint response model.
    """

    status: str = Field(..., description="Overall health status ('ok' or 'degraded')")
    environment: str = Field(..., description="Current running environment")
    database_connected: bool = Field(..., description="Neon PostgreSQL connection pool status")
    redis_connected: bool = Field(..., description="Upstash Redis connection pool status")
    embedding_model_loaded: bool = Field(..., description="SentenceTransformers singleton status")
    timestamp: str = Field(..., description="ISO 8601 server timestamp")
