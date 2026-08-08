from typing import Optional
from pydantic import BaseModel, Field, field_validator


class RecommendationRequest(BaseModel):
    """
    Request payload for AI Menu Dish Recommendations.
    Uses semantic vector similarity + optional category name and price filtering.
    """

    user_craving: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="Natural language description of user's food craving or taste preference.",
        examples=["I want momo", "something refreshing to drink", "spicy chicken"],
    )
    max_price: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Optional maximum price threshold for filtering dishes.",
        examples=[200.00],
    )
    category: Optional[str] = Field(
        default=None,
        max_length=100,
        description=(
            "Optional category name filter (case-insensitive, partial match). "
            "e.g. 'Veg', 'Chicken', 'Tea', 'Summer Drink'"
        ),
        examples=["Veg", "Chicken", "Tea"],
    )
    top_n: int = Field(
        default=3,
        ge=1,
        le=50,
        description="Number of top matching recommendations to return.",
        examples=[3],
    )

    @field_validator("user_craving", mode="before")
    @classmethod
    def sanitize_craving(cls, v: str) -> str:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("user_craving cannot be empty or whitespace.")
        return v

    @field_validator("category", mode="before")
    @classmethod
    def sanitize_category(cls, v: Optional[str]) -> Optional[str]:
        if v and isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v
