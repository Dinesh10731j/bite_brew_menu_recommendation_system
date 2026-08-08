from typing import Any, Dict, List, Optional
from uuid import UUID
from psycopg import AsyncConnection
from psycopg.rows import dict_row

from app.core.logger import logger


class MenuRepository:
    """
    Repository handling PostgreSQL queries for the 'menu_items' table
    utilizing pgvector similarity search (<-> Euclidean distance operator).
    """

    def __init__(self, conn: AsyncConnection) -> None:
        self.conn = conn

    @staticmethod
    def _format_vector(vector: List[float]) -> str:
        """Formats a float list into PostgreSQL vector string format '[x1,x2,...]'."""
        return f"[{','.join(str(val) for val in vector)}]"

    async def get_catalog_items(
        self,
        max_price: Optional[float] = None,
        category: Optional[str] = None,
        top_n: int = 20,
    ) -> List[Dict[str, Any]]:
        """Returns a dynamic full menu catalog from the database, ordered by popularity and name."""
        where_clauses = ["COALESCE(available, TRUE) = TRUE"]
        params: List[Any] = []

        if max_price is not None:
            where_clauses.append("price::numeric <= %s")
            params.append(max_price)

        if category:
            category_value = category.strip()
            normalized = category_value.lower()
            if normalized not in {"all", "all categories", "all-categories", "all_categories"}:
                where_clauses.append(
                    "(COALESCE(c.name, menu_items.category) ILIKE %s OR menu_items.category ILIKE %s)"
                )
                like_pattern = f"%{category_value}%"
                params.append(like_pattern)
                params.append(like_pattern)

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
                c.name AS cat_name
            FROM menu_items
            LEFT JOIN categories c ON c.id = menu_items."categoryId"
            WHERE {where_sql}
            ORDER BY COALESCE(menu_items.popularity, 0) DESC, menu_items.name ASC
            LIMIT %s;
        """

        try:
            async with self.conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql, params)
                rows = await cur.fetchall()
                results = []
                for row in rows:
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
                        "match_score": 1.0,
                        "distance": 0.0,
                    })
                return results
        except Exception as e:
            logger.error(f"Error executing full menu catalog query: {str(e)}")
            raise e

    async def search_dishes_by_vector(
        self,
        query_vector: List[float],
        max_price: Optional[float] = None,
        category: Optional[str] = None,
        top_n: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Performs hybrid vector similarity search using pgvector's Euclidean L2 distance operator (<->),
        combining vector indexing with optional category name and price pre-filters.
        Category filter is case-insensitive and partial-match. The response's 'category' field is built
        as an object {id, name} by LEFT JOINing the relational 'categories' table on menu_items."categoryId".
        """
        vector_str = self._format_vector(query_vector)

        # Dynamic WHERE clause construction
        # Always require embedding and that the item is available
        where_clauses = ["embedding IS NOT NULL", "COALESCE(available, TRUE) = TRUE"]
        params: List[Any] = [vector_str]

        if max_price is not None:
            where_clauses.append("price::numeric <= %s")
            params.append(max_price)

        if category:
            # Case-insensitive partial match against the category name.
            # Match against the JOINed categories.name (preferred) and menu_items.category as fallback.
            where_clauses.append(
                "(COALESCE(c.name, menu_items.category) ILIKE %s OR menu_items.category ILIKE %s)"
            )
            like_pattern = f"%{category}%"
            params.append(like_pattern)
            params.append(like_pattern)

        where_sql = " AND ".join(where_clauses)
        params.append(top_n)

        # SQL Query selecting dishes ordered by pgvector L2 distance operator (<->).
        # LEFT JOIN categories so we can surface the category id + name in the response.
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
                results = []
                for row in rows:
                    dist = float(row["distance"])
                    # Match score formula: bounded between 0.0 and 1.0
                    match_score = round(1.0 / (1.0 + dist), 4)
                    dish_id = str(row["id"]) if isinstance(row["id"], UUID) else row["id"]
                    cat_id = (
                        str(row.get("categoryId"))
                        if isinstance(row.get("categoryId"), UUID)
                        else row.get("categoryId")
                    )
                    img_src = row.get("image") or row.get("image_url")

                    # Handle price parsing safely
                    raw_price = row.get("price")
                    parsed_price = float(raw_price) if raw_price is not None else 0.0

                    # Handle discount parsing safely
                    raw_discount = row.get("discount")
                    parsed_discount = float(raw_discount) if raw_discount is not None else 0.0

                    # Build category as an object {id, name} from the JOINed categories table.
                    # Falls back to the plain menu_items.category string when no join row exists.
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
        except Exception as e:
            logger.error(f"Error executing pgvector search query: {str(e)}")
            raise e

    async def get_dishes_missing_embeddings(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Fetches menu items where embedding IS NULL for batch processing scripts.
        """
        sql = """
            SELECT id, name, description
            FROM menu_items
            WHERE embedding IS NULL
            LIMIT %s;
        """
        try:
            async with self.conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql, [limit])
                rows = await cur.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching items missing embeddings: {str(e)}")
            return []

    async def update_item_embedding(self, item_id: Any, vector: List[float]) -> bool:
        """
        Updates the vector embedding column for a specific menu item.
        """
        vector_str = self._format_vector(vector)
        sql = """
            UPDATE menu_items
            SET embedding = %s::vector,
                updated_at = NOW()
            WHERE id = %s;
        """
        try:
            async with self.conn.cursor() as cur:
                await cur.execute(sql, [vector_str, item_id])
                await self.conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating embedding for item_id={item_id}: {str(e)}")
            await self.conn.rollback()
            return False
