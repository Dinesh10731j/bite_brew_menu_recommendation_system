from typing import Any, Dict, List, Optional
from psycopg import AsyncConnection

from app.core.config import settings
from app.core.logger import logger
from app.core.redis import get_cached_response, set_cached_response
from app.db.user_repository import UserRepository
from app.models.embedder import TextEmbedder
from app.schemas.personalization import (
    PersonalizedRecommendationRequest,
    PersonalizedRecommendationResponse,
    UserPreferenceSummary,
)
from app.schemas.response import DishRecommendation


class PersonalizationService:
    """
    Orchestrates AI personalized recommendations based on a user's
    behavior events and order history.

    Logic:
      1. Gather signal dish embeddings from the user's events/orders.
      2. Average them into a composite 'preference vector' (taste profile).
      3. Optionally blend with a craving text embedding.
      4. Run pgvector nearest-neighbor search, excluding already-ordered items.
      5. Persist the learned preference profile for future fast lookups.
    """

    def __init__(
        self,
        embedder: TextEmbedder,
        db_conn: Optional[AsyncConnection] = None,
    ) -> None:
        self.embedder = embedder
        self.db_conn = db_conn

    def _average_vectors(self, vectors: List[List[float]]) -> Optional[List[float]]:
        """Averages a list of equal-length float vectors. Returns None if empty."""
        if not vectors:
            return None
        dim = len(vectors[0])
        if dim == 0:
            return None
        avg = [0.0] * dim
        for vec in vectors:
            for i in range(dim):
                avg[i] += vec[i]
        avg = [v / len(vectors) for v in avg]
        return avg

    def _blend_vectors(
        self,
        preference: List[float],
        craving: Optional[List[float]],
        preference_weight: float = 0.7,
    ) -> List[float]:
        """
        Blends the user preference vector with an optional craving vector.
        Default: 70% preference, 30% craving.
        """
        if craving is None:
            return preference
        if len(preference) != len(craving):
            return preference
        return [
            (preference_weight * p) + ((1.0 - preference_weight) * c)
            for p, c in zip(preference, craving)
        ]

    async def capture_event(
        self,
        user_id: str,
        menu_item_id: Any,
        event_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Records a behavior event and refreshes the user's preference profile."""
        if self.db_conn is None:
            raise RuntimeError("No active database connection available.")

        repo = UserRepository(self.db_conn)
        event_id = await repo.track_event(
            user_id=user_id,
            menu_item_id=menu_item_id,
            event_type=event_type,
            metadata=metadata,
        )
        # Async refresh of the profile (best-effort)
        await self._refresh_preference_profile(repo, user_id)
        return event_id

    async def record_order(
        self,
        user_id: str,
        items: List[Dict[str, Any]],
        total: Optional[float],
        status: str = "completed",
    ) -> int:
        """Records an order and refreshes the user's preference profile."""
        if self.db_conn is None:
            raise RuntimeError("No active database connection available.")

        repo = UserRepository(self.db_conn)
        order_id = await repo.record_order(
            user_id=user_id, items=items, total=total, status=status
        )
        await self._refresh_preference_profile(repo, user_id)
        return order_id

    async def _refresh_preference_profile(
        self, repo: UserRepository, user_id: str
    ) -> None:
        """
        Recomputes and persists the user's preference vector + favorite categories.
        Best-effort; failures are logged but not fatal.
        """
        try:
            vectors = await repo.get_signal_dish_descriptions(user_id)
            avg = self._average_vectors(vectors)
            fav_cats = await repo.get_favorite_categories(user_id)
            if avg is not None:
                await repo.save_preference_profile(
                    user_id, avg, fav_cats
                )
        except Exception as e:
            logger.warning(f"Could not refresh preference profile for user={user_id}: {str(e)}")

    async def get_personalized_recommendations(
        self,
        user_id: str,
        request: PersonalizedRecommendationRequest,
    ) -> PersonalizedRecommendationResponse:
        """
        Generates personalized recommendations from the user's learned profile.
        """
        # Cache key derived from user + request params
        raw_key = (
            f"personalized:{user_id}:"
            f"{(request.user_craving or '').strip().lower()}:"
            f"{request.max_price}:"
            f"{request.category}:"
            f"{request.top_n}"
        )
        import hashlib
        cache_key = f"personalized_v1:{hashlib.sha256(raw_key.encode('utf-8')).hexdigest()}"

        cached_data = await get_cached_response(cache_key)
        if cached_data:
            logger.info(f"Serving personalized response from cache (user={user_id})")
            cached_data["cached"] = True
            return PersonalizedRecommendationResponse(**cached_data)

        if self.db_conn is None:
            raise RuntimeError("No active database connection available.")

        repo = UserRepository(self.db_conn)

        # 1. Gather behavior/order signal vectors
        signal_vectors = await repo.get_signal_dish_descriptions(user_id)
        preference_vector = self._average_vectors(signal_vectors)

        fav_categories = await repo.get_favorite_categories(user_id)
        counts = await repo.get_user_activity_counts(user_id)

        total_matches = 0
        recommendations: List[DishRecommendation] = []

        if preference_vector is not None:
            # 2. Optionally blend with craving vector
            blended = preference_vector
            craving = None
            if request.user_craving:
                craving = self.embedder.encode_text(request.user_craving)
                blended = self._blend_vectors(preference_vector, craving)

            # 3. Search, excluding already-ordered items
            excluded = await repo.get_user_ordered_item_ids(user_id)
            rows = await repo.personalized_search(
                preference_vector=blended,
                max_price=request.max_price,
                category=request.category,
                top_n=request.top_n,
                exclude_ids=excluded,
            )
            recommendations = [DishRecommendation(**item) for item in rows]
            total_matches = len(recommendations)

            # 4. Persist learned profile
            await repo.save_preference_profile(user_id, blended, fav_categories)
        else:
            logger.info(
                f"No behavioral signal yet for user={user_id}. "
                "Returning empty personalized set until events/orders are captured."
            )

        response = PersonalizedRecommendationResponse(
            user_id=user_id,
            status="success",
            query_craving=request.user_craving,
            filters_applied={
                "max_price": request.max_price,
                "category": request.category,
            },
            preference_summary=UserPreferenceSummary(
                favorite_categories=fav_categories,
                total_orders=counts.get("total_orders", 0),
                total_events=counts.get("total_events", 0),
                has_preference_profile=preference_vector is not None,
            ),
            total_matches=total_matches,
            recommendations=recommendations,
            cached=False,
        )

        await set_cached_response(
            cache_key,
            response.model_dump(),
            ttl=settings.CACHE_TTL_SECONDS,
        )

        return response
