from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class UserEventRequest(BaseModel):
    """
    Request payload for capturing a user behavior event
    (view, like, favorite, add_to_cart, click).
    """

    menu_item_id: Union[int, str, UUID] = Field(
        ...,
        description="Identifier of the menu item the user interacted with.",
        examples=[1, "6937aa7d-b073-42dd-a449-7595c884c480"],
    )
    event_type: str = Field(
        ...,
        description="Type of behavior event. One of: view, like, favorite, add_to_cart, click.",
        examples=["view", "like", "favorite", "add_to_cart", "click"],
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional extra context (e.g. source page, quantity, timestamp).",
    )

    @field_validator("event_type", mode="before")
    @classmethod
    def sanitize_event_type(cls, v: str) -> str:
        allowed = {"view", "like", "favorite", "add_to_cart", "click", "order"}
        if isinstance(v, str):
            v = v.strip().lower()
            if v not in allowed:
                raise ValueError(
                    f"event_type must be one of: {', '.join(sorted(allowed))}"
                )
            return v
        return v


class UserOrderItem(BaseModel):
    """A single menu item within an order."""

    menu_item_id: Union[int, str, UUID] = Field(
        ..., description="Identifier of the ordered menu item."
    )
    quantity: int = Field(default=1, ge=1, description="Quantity ordered.")
    price: Optional[float] = Field(default=None, ge=0.0, description="Unit price.")


class UserOrderRequest(BaseModel):
    """Request payload for recording a user's order history."""

    items: List[UserOrderItem] = Field(
        ..., min_length=1, description="List of menu items included in the order."
    )
    total: Optional[float] = Field(default=None, ge=0.0, description="Order total.")
    status: str = Field(default="completed", description="Order status.")

    @field_validator("status", mode="before")
    @classmethod
    def sanitize_status(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip() or "completed"
        return "completed"


class PersonalizedRecommendationRequest(BaseModel):
    """
    Request payload for generating AI personalized recommendations
    based on a user's behavior and order history.
    """

    user_craving: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=500,
        description=(
            "Optional natural language craving to blend with the user's "
            "taste profile. If omitted, recommendations are purely history-based."
        ),
        examples=["I love spicy momo", "something refreshing"],
    )
    max_price: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Optional maximum price threshold.",
        examples=[200.00],
    )
    category: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional category name filter (case-insensitive).",
        examples=["Veg", "Chicken"],
    )
    top_n: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of personalized recommendations to return.",
        examples=[5],
    )

    @field_validator("user_craving", mode="before")
    @classmethod
    def sanitize_craving(cls, v: Optional[str]) -> Optional[str]:
        if v and isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v

    @field_validator("category", mode="before")
    @classmethod
    def sanitize_category(cls, v: Optional[str]) -> Optional[str]:
        if v and isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v


class UserPreferenceSummary(BaseModel):
    """Summary of the user's learned taste profile."""

    favorite_categories: List[str] = Field(
        default_factory=list, description="Top categories the user prefers."
    )
    total_orders: int = Field(default=0, description="Total number of orders placed.")
    total_events: int = Field(default=0, description="Total behavior events tracked.")
    has_preference_profile: bool = Field(
        default=False, description="Whether a learned preference profile exists."
    )


class PersonalizedRecommendationResponse(BaseModel):
    """
    Top-level response for personalized recommendations.
    """

    user_id: str = Field(..., description="The user for whom recommendations were generated.")
    status: str = Field(default="success", description="Response status message.")
    query_craving: Optional[str] = Field(
        default=None, description="Echo of the optional craving query."
    )
    filters_applied: Dict[str, Any] = Field(
        default_factory=dict, description="Active pre-filters applied."
    )
    preference_summary: UserPreferenceSummary = Field(
        ..., description="Learned user preference summary."
    )
    total_matches: int = Field(..., description="Number of recommendations returned.")
    recommendations: List[Any] = Field(
        default_factory=list, description="List of personalized dish recommendations."
    )
    cached: bool = Field(default=False, description="Whether served from cache.")


class EventProcessedResponse(BaseModel):
    """Acknowledgment for a captured user event."""

    status: str = Field(default="success", description="Response status.")
    user_id: str = Field(..., description="The user the event was recorded for.")
    event_type: str = Field(..., description="Type of event captured.")
    menu_item_id: Any = Field(..., description="Menu item the event relates to.")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp of event capture.",
    )


class OrderProcessedResponse(BaseModel):
    """Acknowledgment for a recorded order."""

    status: str = Field(default="success", description="Response status.")
    user_id: str = Field(..., description="The user the order was recorded for.")
    order_id: int = Field(..., description="Database id of the created order.")
    total: float = Field(..., description="Order total.")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp of order recording.",
    )
