import json
from typing import Any, Dict, List, Optional
from uuid import UUID
from psycopg import AsyncConnection
from psycopg.rows import dict_row

from app.core.logger import logger


class UserRepository:
    """
    Repository handling user behavior events, order history, preference
    profiles, and personalized vector search for the recommendation system.
    """

    def __init__(self, conn: AsyncConnection) -> None:
        self.conn = conn

    @staticmethod
    def _format_vector(vector: List[float]) -> str:
        """Formats a float list into PostgreSQL vector string format '[x1,x2,...]'."""
        return f"[{','.join(str(val) for val in vector)}]"

    async def track_event(
        self,
        user_id: str,
        menu_item_id: Any,
        event_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Records a user behavior event and returns the new event id."""
        sql = """
            INSERT INTO user_events (user_id, menu_item_id, event_type, metadata)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
        """
        meta_json = json.dumps(metadata) if metadata else None
        try:
            async with self.conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql, [user_id, menu_item_id, event_type, meta_json])
                row = await cur.fetchone()
                await self.conn.commit()
                return row["id"] if row else 0
        except Exception as e:
            logger.error(f"Error tracking user event: {str(e)}")
            await self.conn.rollback()
            raise e

    async def record_order(
        self,
        user_id: str,
        items: List[Dict[str, Any]],
        total: Optional[float],
        status: str = "completed",
    ) -> int:
        """
        Records an order and its items, also inserts order events for each
        item so order history contributes to the preference profile.
        Returns the new order id.
        """
        try:
            async with self.conn.cursor(row_factory=dict_row) as cur:
                # Create the order
                await cur.execute(
                    """
                    INSERT INTO user_orders (user_id, total, status)
                    VALUES (%s, %s, %s)
                    RETURNING id;
                    """,
                    [user_id, total, status],
                )
                order_row = await cur.fetchone()
                order_id = order_row["id"]

                # Insert order items
                for item in items:
                    await cur.execute(
                        """
                        INSERT INTO user_order_items
                            (order_id, menu_item_id, quantity, price)
                        VALUES (%s, %s, %s, %s);
                        """,
                        [
                            order_id,
                            item.get("menu_item_id"),
                            item.get("quantity", 1),
                            item.get("price"),
                        ],
                    )
                    # Also record an 'order' event to feed the preference profile
                    await cur.execute(
                        """
                        INSERT INTO user_events
                            (user_id, menu_item_id, event_type, metadata)
                        VALUES (%s, %s, %s, %s);
                        """,
                        [
                            user_id,
                            item.get("menu_item_id"),
                            "order",
                            json.dumps({"order_id": order_id, "quantity": item.get("quantity", 1)}),
                        ],
                    )

                await self.conn.commit()
                return order_id
        except Exception as e:
            logger.error(f"Error recording user order: {str(e)}")
            await self.conn.rollback()
            raise e

    async def get_user_ordered_item_ids(self, user_id: str) -> List[int]:
        """Returns distinct menu_item_ids the user has ordered (for exclusion)."""
        sql = """
            SELECT DISTINCT oi.menu_item_id
            FROM user_order_items oi
            JOIN user_orders o ON o.id = oi.order_id
            WHERE o.user_id = %s AND oi.menu_item_id IS NOT NULL;
        """
        try:
            async with self.conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql, [user_id])
                rows = await cur.fetchall()
                return [int(r["menu_item_id"]) for r in rows]
        except Exception as e:
            logger.error(f"Error fetching user ordered items: {str(e)}")
            return []

    async def get_favorite_categories(self, user_id: str, limit: int = 5) -> List[str]:
        """
        Computes the user's most-order categories as a simple preference signal.
        Groups orders by menu_items.category / joined categories name.
        """
        sql = """
            SELECT COALESCE(c.name, mi.category) AS cat
            FROM user_order_items oi
            JOIN user_orders o ON o.id = oi.order_id
            JOIN menu_items mi ON mi.id = oi.menu_item_id
            LEFT JOIN categories c ON c.id = mi."categoryId"
            WHERE o.user_id = %s
            GROUP BY COALESCE(c.name, mi.category)
            ORDER BY COUNT(*) DESC
            LIMIT %s;
        """
        try:
            async with self.conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql, [user_id, limit])
                rows = await cur.fetchall()
                return [r["cat"] for r in rows if r["cat"]]
        except Exception as e:
            logger.error(f"Error fetching favorite categories: {str(e)}")
            return []

    async def get_user_activity_counts(self, user_id: str) -> Dict[str, int]:
        """Returns total orders and total events for a user."""
        order_q = "SELECT COUNT(*) AS c FROM user_orders WHERE user_id = %s;"
        event_q = "SELECT COUNT(*) AS c FROM user_events WHERE user_id = %s;"
        try:
            async with self.conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(order_q, [user_id])
                orders = await cur.fetchone()
                await cur.execute(event_q, [user_id])
                events = await cur.fetchone()
                return {
                    "total_orders": int(orders["c"]) if orders else 0,
                    "total_events": int(events["c"]) if events else 0,
                }
        except Exception as e:
            logger.error(f"Error fetching user activity counts: {str(e)}")
            return {"total_orders": 0, "total_events": 0}

    async def get_signal_dish_descriptions(
        self, user_id: str, limit: int = 20
    ) -> List[List[float]]:
        """
        Retrieves the embeddings of dishes the user has interacted with or
        ordered, weighted by recency/frequency. Returns a list of vectors.
        """
        sql = """
            SELECT mi.embedding
            FROM (
                SELECT mi.id, mi.embedding,
                       COUNT(*) AS cnt,
                       MAX(e.created_at) AS last_ts
                FROM user_events e
                JOIN menu_items mi ON mi.id = e.menu_item_id
                WHERE e.user_id = %s AND mi.embedding IS NOT NULL
                GROUP BY mi.id, mi.embedding
                ORDER BY cnt DESC, last_ts DESC
                LIMIT %s
            ) mi
            WHERE mi.embedding IS NOT NULL;
        """
        try:
            async with self.conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql, [user_id, limit])
                rows = await cur.fetchall()
                vectors = []
                for r in rows:
                    vec = r.get("embedding")
                    if vec is not None:
                        # psycopg returns vector as a list of floats
                        vectors.append(list(vec))
                return vectors
        except Exception as e:
            logger.error(f"Error fetching signal dish embeddings: {str(e)}")
            return []

    async def save_preference_profile(
        self, user_id: str, preference_vector: List[float], favorite_categories: List[str]
    ) -> None:
        """Upserts the aggregated preference profile for a user."""
        vec_str = self._format_vector(preference_vector)
        cats_json = json.dumps(favorite_categories)
        sql = """
            INSERT INTO user_preference_profile
                (user_id, preference_vector, favorite_categories, last_updated_at)
            VALUES (%s, %s::vector, %s, NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET
                preference_vector = EXCLUDED.preference_vector,
                favorite_categories = EXCLUDED.favorite_categories,
                last_updated_at = NOW();
        """
        try:
            async with self.conn.cursor() as cur:
                await cur.execute(sql, [user_id, vec_str, cats_json])
                await self.conn.commit()
        except Exception as e:
            logger.error(f"Error saving preference profile: {str(e)}")
            await self.conn.rollback()

    async def personalized_search(
        self,
        preference_vector: List[float],
        max_price: Optional[float] = None,
        category: Optional[str] = None,
        top_n: int = 5,
        exclude_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Performs pgvector similarity search using the user's preference vector,
        with optional price/category filters and exclusion of already-ordered items.
        """
        vector_str = self._format_vector(preference_vector)

        where_clauses = ["embedding IS NOT NULL", "COALESCE(available, TRUE) = TRUE"]
        params: List[Any] = [vector_str]

        if max_price is not None:
            where_clauses.append("price::numeric <= %s")
            params.append(max_price)

        if category:
            where_clauses.append(
                "(COALESCE(c.name, menu_items.category) ILIKE %s OR menu_items.category ILIKE %s)"
            )
            like = f"%{category}%"
            params.append(like)
            params.append(like)

        if exclude_ids:
            placeholders = ", ".join(["%s"] * len(exclude_ids))
            where_clauses.append(f"menu_items.id NOT IN ({placeholders})")
            params.extend([int(i) for i in exclude_ids])

        where_sql = " AND ".join(where_clauses)
        params.append(top_n)

        sql = f"""
            SELECT
                menu_items.id,
                menu_items.name,
                menu_items.description,
                menu_items.price,
                menu_items.image,
                menu_items.image_url,
                menu_items.category,
                menu_items."categoryId",
                menu_items.available,
                menu_items.featured,
                menu_items.discount,
                menu_items.popularity,
                menu_items.is_vegetarian,
                c.id AS cat_id,
                c.name AS cat_name,
                (menu_items.embedding <-> %s::vector) AS distance
            FROM menu_items
            LEFT JOIN categories c ON c.id = menu_items."categoryId"
            WHERE {where_sql}
            ORDER BY distance ASC
            LIMIT %s;
        """

        try:
            async with self.conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql, params)
                rows = await cur.fetchall()
                return self._build_dish_rows(rows)
        except Exception as e:
            logger.error(f"Error executing personalized search: {str(e)}")
            raise e

    def _build_dish_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Converts raw DB rows into DishRecommendation-compatible dicts."""
        results = []
        for row in rows:
            dist = float(row["distance"])
            match_score = round(1.0 / (1.0 + dist), 4)
            dish_id = str(row["id"]) if isinstance(row["id"], UUID) else row["id"]
            cat_id = (
                str(row.get("categoryId"))
                if isinstance(row.get("categoryId"), UUID)
                else row.get("categoryId")
            )
            img_src = row.get("image") or row.get("image_url")

            raw_price = row.get("price")
            parsed_price = float(raw_price) if raw_price is not None else 0.0
            raw_discount = row.get("discount")
            parsed_discount = float(raw_discount) if raw_discount is not None else 0.0

            joined_cat_id = row.get("cat_id")
            joined_cat_name = row.get("cat_name")
            if joined_cat_id is not None or joined_cat_name is not None:
                category_obj = {
                    "id": (
                        str(joined_cat_id)
                        if isinstance(joined_cat_id, UUID)
                        else joined_cat_id
                    ),
                    "name": joined_cat_name,
                    "description": None,
                }
            else:
                category_obj = row.get("category")

            results.append({
                "id": dish_id,
                "name": row["name"],
                "description": row["description"],
                "price": parsed_price,
                "image": img_src,
                "image_url": img_src,
                "category": category_obj,
                "categoryId": cat_id,
                "available": bool(row.get("available")) if row.get("available") is not None else True,
                "featured": bool(row.get("featured")) if row.get("featured") is not None else False,
                "discount": parsed_discount,
                "popularity": int(row.get("popularity", 0)) if row.get("popularity") is not None else 0,
                "is_vegetarian": bool(row.get("is_vegetarian")) if row.get("is_vegetarian") is not None else True,
                "match_score": match_score,
                "distance": round(dist, 4),
            })
        return results
