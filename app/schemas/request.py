from typing import Optional
from pydantic import BaseModel, Field, field_validator


class RecommendationRequest(BaseModel):
    """
    Request payload for AI Menu Dish Recommendations.
    """

    user_craving: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="Natural language description of user's food craving, mood, or taste preference.",
        examples=["I want something spicy and cheesy for lunch"],
    )
    max_price: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Optional maximum price threshold for filtering dishes.",
        examples=[20.00],
    )
    is_vegetarian: Optional[bool] = Field(
        default=None,
        description="Optional dietary constraint filtering for vegetarian dishes.",
        examples=[True],
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
