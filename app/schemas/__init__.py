"""
Pydantic Data Transfer Objects (DTOs) for request & response validation.
"""

from app.schemas.request import RecommendationRequest
from app.schemas.response import (
    DishRecommendation,
    RecommendationResponse,
    HealthCheckResponse,
)
from app.schemas.personalization import (
    UserEventRequest,
    UserOrderRequest,
    UserOrderItem,
    PersonalizedRecommendationRequest,
    PersonalizedRecommendationResponse,
    UserPreferenceSummary,
    EventProcessedResponse,
    OrderProcessedResponse,
)

__all__ = [
    "RecommendationRequest",
    "DishRecommendation",
    "RecommendationResponse",
    "HealthCheckResponse",
    "UserEventRequest",
    "UserOrderRequest",
    "UserOrderItem",
    "PersonalizedRecommendationRequest",
    "PersonalizedRecommendationResponse",
    "UserPreferenceSummary",
    "EventProcessedResponse",
    "OrderProcessedResponse",
]

