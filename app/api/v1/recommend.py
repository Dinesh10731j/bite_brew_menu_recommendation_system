from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_recommendation_service
from app.core.logger import logger
from app.schemas.request import RecommendationRequest
from app.schemas.response import RecommendationResponse
from app.services.recommendation import RecommendationService

router = APIRouter(tags=["Recommendations"])


@router.post(
    "/recommend",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate AI Menu Dish Recommendations",
    description=(
        "Converts natural language user cravings into 384-dimensional vector embeddings, "
        "executing pgvector similarity search (<-> operator) combined with price and dietary pre-filters."
    ),
)
async def get_menu_recommendations(
    payload: RecommendationRequest,
    service: RecommendationService = Depends(get_recommendation_service),
) -> RecommendationResponse:
    """
    POST route handling user food craving recommendations.
    """
    try:
        response = await service.get_recommendations(payload)
        return response
    except ValueError as ve:
        logger.warning(f"Validation error in recommendation route: {str(ve)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Unhandled error in recommendation route: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred while processing recommendations.",
        )
