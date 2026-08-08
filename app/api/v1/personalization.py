from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import get_personalization_service
from app.core.config import settings
from app.core.logger import logger
from app.core.rate_limit import limiter
from app.schemas.personalization import (
    UserEventRequest,
    UserOrderRequest,
    UserOrderItem,
    PersonalizedRecommendationRequest,
    PersonalizedRecommendationResponse,
    EventProcessedResponse,
    OrderProcessedResponse,
)
from app.services.personalization import PersonalizationService

router = APIRouter(tags=["Personalization"])


@router.post(
    "/users/{user_id}/events",
    response_model=EventProcessedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Capture User Behavior Event",
    description="Records a user behavior event (view, like, favorite, add_to_cart, click) to train AI recommendations.",
)
@limiter.limit(settings.EVENT_RATE_LIMIT)
async def capture_user_event(
    request: Request,
    user_id: str,
    payload: UserEventRequest,
    service: PersonalizationService = Depends(get_personalization_service),
) -> EventProcessedResponse:
    """
    Captures a single user behavior event. The event feeds the user's
    learned taste profile for future personalized recommendations.
    """
    try:
        await service.capture_event(
            user_id=user_id,
            menu_item_id=payload.menu_item_id,
            event_type=payload.event_type,
            metadata=payload.metadata,
        )
        return EventProcessedResponse(
            user_id=user_id,
            event_type=payload.event_type,
            menu_item_id=payload.menu_item_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        logger.error(f"Unhandled error capturing user event: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to capture user event.",
        )


@router.post(
    "/users/{user_id}/orders",
    response_model=OrderProcessedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record User Order History",
    description="Records a user's order (with items) to personalize future recommendations.",
)
@limiter.limit(settings.ORDER_RATE_LIMIT)
async def record_user_order(
    request: Request,
    user_id: str,
    payload: UserOrderRequest,
    service: PersonalizationService = Depends(get_personalization_service),
) -> OrderProcessedResponse:
    """
    Records an order into the user's history. Ordered items become strong
    preference signals in the AI recommendation engine.
    """
    try:
        items = [
            UserOrderItem(**item).model_dump()
            if isinstance(item, dict)
            else item.model_dump()
            for item in payload.items
        ]
        order_id = await service.record_order(
            user_id=user_id,
            items=items,
            total=payload.total,
            status=payload.status,
        )
        return OrderProcessedResponse(
            user_id=user_id,
            order_id=order_id,
            total=payload.total if payload.total is not None else 0.0,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        logger.error(f"Unhandled error recording user order: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record user order.",
        )


@router.get(
    "/users/{user_id}/recommendations",
    response_model=PersonalizedRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get AI Personalized Recommendations",
    description=(
        "Returns dish recommendations personalized to a user based on their "
        "behavior events and order history. Optionally blends a craving text query."
    ),
)
@limiter.limit(settings.PERSONALIZED_RECOMMEND_RATE_LIMIT)
async def get_personalized_recommendations(
    request: Request,
    user_id: str,
    user_craving: Optional[str] = Query(None, description="Optional craving text to blend in."),
    max_price: Optional[float] = Query(None, gt=0.0, description="Max price filter."),
    category: Optional[str] = Query(None, max_length=100, description="Category name filter."),
    top_n: int = Query(5, ge=1, le=50, description="Number of recommendations."),
    service: PersonalizationService = Depends(get_personalization_service),
) -> PersonalizedRecommendationResponse:
    """
    Generates personalized dish recommendations from learned user behavior
    and order history, blended with an optional live craving query.
    """
    try:
        personalized_request = PersonalizedRecommendationRequest(
            user_craving=user_craving,
            max_price=max_price,
            category=category,
            top_n=top_n,
        )
        return await service.get_personalized_recommendations(user_id, personalized_request)
    except ValueError as ve:
        logger.warning(f"Validation error in personalized recommendations: {str(ve)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Unhandled error in personalized recommendations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred while generating personalized recommendations.",
        )
