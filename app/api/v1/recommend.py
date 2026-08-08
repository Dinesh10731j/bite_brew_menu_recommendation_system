from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import get_recommendation_service
from app.core.config import settings
from app.core.logger import logger
from app.core.rate_limit import limiter
from app.db.repository import MenuRepository
from app.schemas.request import RecommendationRequest
from app.schemas.response import (
    DishRecommendation,
    MenuCatalogResponse,
    RecommendationFiltersApplied,
    RecommendationResponse,
)
from app.services.recommendation import RecommendationService

router = APIRouter(tags=["Recommendations"])


@router.get(
    "/menu",
    response_model=MenuCatalogResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the full dynamic menu catalog from the database",
    description="Returns the live menu catalog with no AI ranking so the frontend can treat it as a full menu list separate from AI recommendations.",
)
@limiter.limit(settings.RECOMMEND_RATE_LIMIT)
async def get_menu_catalog(
    request: Request,
    max_price: float | None = Query(None, gt=0.0, description="Optional maximum price threshold."),
    category: str | None = Query(None, max_length=100, description="Optional category filter."),
    top_n: int = Query(20, ge=1, le=50, description="Number of menu items to return."),
    service: RecommendationService = Depends(get_recommendation_service),
) -> MenuCatalogResponse:
    """Returns the live database catalog for the full menu view."""
    try:
        if service.db_conn is None:
            recommendations = []
        else:
            repo = MenuRepository(service.db_conn)
            recommendations_data = await repo.get_catalog_items(
                max_price=max_price,
                category=category,
                top_n=top_n,
            )
            recommendations = [
                {
                    **item,
                    "match_score": float(item.get("match_score", 1.0)),
                    "distance": float(item.get("distance", 0.0)),
                }
                for item in recommendations_data
            ]

        return MenuCatalogResponse(
            status="success",
            source="full_catalog",
            query_craving="",
            filters_applied=RecommendationFiltersApplied(
                max_price=max_price,
                category=category,
            ),
            total_matches=len(recommendations),
            recommendations=[DishRecommendation(**item) for item in recommendations],
            cached=False,
        )
    except Exception as e:
        logger.error(f"Unhandled error fetching menu catalog: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred while loading the full menu catalog.",
        )


@router.get(
    "/catalog",
    include_in_schema=False,
    response_model=MenuCatalogResponse,
    status_code=status.HTTP_200_OK,
)
async def get_menu_catalog_alias(
    request: Request,
    max_price: float | None = Query(None, gt=0.0, description="Optional maximum price threshold."),
    category: str | None = Query(None, max_length=100, description="Optional category filter."),
    top_n: int = Query(20, ge=1, le=50, description="Number of menu items to return."),
    service: RecommendationService = Depends(get_recommendation_service),
) -> MenuCatalogResponse:
    return await get_menu_catalog(request, max_price, category, top_n, service)


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
@limiter.limit(settings.RECOMMEND_RATE_LIMIT)
async def get_menu_recommendations(
    request: Request,
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
