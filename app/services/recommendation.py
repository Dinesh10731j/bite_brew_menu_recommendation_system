import hashlib
from typing import Any, Dict, List, Optional
from psycopg import AsyncConnection

from app.core.config import settings
from app.core.logger import logger
from app.core.redis import get_cached_response, set_cached_response
from app.db.repository import MenuRepository
from app.models.embedder import TextEmbedder
from app.schemas.request import RecommendationRequest
from app.schemas.response import (
    DishRecommendation,
    RecommendationFiltersApplied,
    RecommendationResponse,
)


class RecommendationService:
    """
    Orchestrates business logic for generating menu dish recommendations.
    Connects vector encoding model, Neon PostgreSQL pgvector similarity queries,
    and Upstash Redis query caching.
    Returns STRICTLY real database records from PostgreSQL — zero mock/external fallback data.
    """

    def __init__(
        self,
        embedder: TextEmbedder,
        db_conn: Optional[AsyncConnection] = None,
    ) -> None:
        self.embedder = embedder
        self.db_conn = db_conn

    def _generate_cache_key(self, request: RecommendationRequest) -> str:
        """Generates a unique SHA256 cache key based on query parameters."""
        raw_key = (
            f"{request.user_craving.strip().lower()}:"
            f"{request.max_price}:"
            f"{request.category}:"
            f"{request.top_n}"
        )
        hashed = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        return f"rec_cache_v2:{hashed}"

    async def get_recommendations(
        self, request: RecommendationRequest
    ) -> RecommendationResponse:
        """
        Processes a recommendation request:
        1. Checks Upstash Redis cache for pre-computed result.
        2. Encodes user craving text into 384-dimensional vector embedding.
        3. Queries Neon PostgreSQL database pgvector (<-> operator) with pre-filters.
        4. Returns strictly real database rows (empty list if no database rows match).
        5. Saves generated response into Redis cache with TTL.
        """
        cache_key = self._generate_cache_key(request)

        # 1. Redis Cache Lookup
        cached_data = await get_cached_response(cache_key)
        if cached_data:
            logger.info(f"Serving recommendation response from Redis cache (key={cache_key})")
            cached_data["cached"] = True
            return RecommendationResponse(**cached_data)

        logger.info(
            f"Cache MISS for key={cache_key}. Computing recommendations for craving='{request.user_craving}' | "
            f"max_price={request.max_price} | category={request.category} | top_n={request.top_n}"
        )

        dishes_data: List[Dict[str, Any]] = []

        # 2. Encode user craving text into 384-dimensional vector embedding
        query_vector = self.embedder.encode_text(request.user_craving)

        # 3. Execute pgvector search query against Neon PostgreSQL database
        if self.db_conn is not None:
            try:
                repo = MenuRepository(self.db_conn)
                dishes_data = await repo.search_dishes_by_vector(
                    query_vector=query_vector,
                    max_price=request.max_price,
                    category=request.category,
                    top_n=request.top_n,
                )
            except Exception as e:
                logger.error(f"Database vector query failed: {str(e)}")
                dishes_data = []
        else:
            logger.warning("No active database connection available.")
            dishes_data = []

        # 4. Assemble response DTOs strictly from PostgreSQL query results
        recommendations = [DishRecommendation(**item) for item in dishes_data]

        response = RecommendationResponse(
            status="success",
            query_craving=request.user_craving,
            filters_applied=RecommendationFiltersApplied(
                max_price=request.max_price,
                category=request.category,
            ),
            total_matches=len(recommendations),
            recommendations=recommendations,
            cached=False,
        )

        # 5. Store computed result in Redis cache
        await set_cached_response(
            cache_key, response.model_dump(), ttl=settings.CACHE_TTL_SECONDS
        )

        return response
