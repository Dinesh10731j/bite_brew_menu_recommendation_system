from __future__ import annotations

from typing import Any, Dict, List, Optional

from psycopg import AsyncConnection

from app.core.logger import logger


class AIRepository:
    """Repository for AI command-center analytics that gracefully handles missing tables."""

    @staticmethod
    async def table_exists(conn: Optional[AsyncConnection], table_name: str) -> bool:
        if conn is None:
            return False
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s)",
                    (table_name,),
                )
                row = await cur.fetchone()
                return bool(row[0]) if row else False
        except Exception as exc:
            logger.warning("Table existence check failed for %s: %s", table_name, exc)
            return False

    @staticmethod
    async def get_metric_summary(conn: Optional[AsyncConnection]) -> Dict[str, Any]:
        snapshot = await AIRepository.get_business_snapshot(conn)
        summary = {
            "has_business_data": snapshot.get("has_data", False),
            "tables": snapshot.get("tables", []),
            "menu_items": snapshot.get("menu_items", 0),
            "orders": snapshot.get("orders", 0),
            "revenue": snapshot.get("revenue", 0.0),
            "recent_orders_30d": snapshot.get("recent_orders_30d", 0),
            "recent_revenue_30d": snapshot.get("recent_revenue_30d", 0.0),
        }
        return summary

    @staticmethod
    async def get_business_snapshot(conn: Optional[AsyncConnection]) -> Dict[str, Any]:
        snapshot: Dict[str, Any] = {
            "has_data": False,
            "tables": [],
            "menu_items": 0,
            "orders": 0,
            "revenue": 0.0,
            "recent_orders_30d": 0,
            "recent_revenue_30d": 0.0,
            "popular_items": [],
            "loyalty_accounts": 0,
            "staff_count": 0,
            "cancelled_orders": 0,
            "daily_revenue": [],
        }
        if conn is None:
            return snapshot

        for table in ("menu_items", "orders", "order_items", "staff", "loyalty_accounts"):
            if await AIRepository.table_exists(conn, table):
                snapshot["tables"].append(table)

        try:
            async with conn.cursor() as cur:
                await cur.execute('SELECT COUNT(*) FROM public."menu_items" WHERE COALESCE("name", \'\') <> \'\'')
                row = await cur.fetchone()
                if row:
                    snapshot["menu_items"] = int(row[0] or 0)
        except Exception:
            snapshot["menu_items"] = 0

        try:
            async with conn.cursor() as cur:
                await cur.execute('SELECT COUNT(*) FROM public."orders"')
                row = await cur.fetchone()
                if row:
                    snapshot["orders"] = int(row[0] or 0)
        except Exception:
            snapshot["orders"] = 0

        try:
            async with conn.cursor() as cur:
                await cur.execute('SELECT COALESCE(SUM("totalPrice"), 0) FROM public."orders" WHERE "totalPrice" > 0')
                row = await cur.fetchone()
                value = float(row[0] or 0) if row else 0.0
                snapshot["revenue"] = value
        except Exception:
            snapshot["revenue"] = 0.0

        try:
            async with conn.cursor() as cur:
                await cur.execute('SELECT COUNT(*) FROM public."orders" WHERE "createdAt" >= NOW() - INTERVAL \'30 days\'')
                row = await cur.fetchone()
                if row:
                    snapshot["recent_orders_30d"] = int(row[0] or 0)
                await cur.execute('SELECT COALESCE(SUM("totalPrice"), 0) FROM public."orders" WHERE "totalPrice" > 0 AND "createdAt" >= NOW() - INTERVAL \'30 days\'')
                row = await cur.fetchone()
                if row:
                    snapshot["recent_revenue_30d"] = float(row[0] or 0)
        except Exception:
            snapshot["recent_orders_30d"] = 0
            snapshot["recent_revenue_30d"] = 0.0

        try:
            async with conn.cursor() as cur:
                await cur.execute('SELECT COUNT(*) FROM public."orders" WHERE LOWER(CAST("status" AS text)) LIKE %s', ('%cancel%',))
                row = await cur.fetchone()
                if row:
                    snapshot["cancelled_orders"] = int(row[0] or 0)
        except Exception:
            snapshot["cancelled_orders"] = 0

        try:
            async with conn.cursor() as cur:
                await cur.execute('SELECT DATE("createdAt") AS day, COALESCE(SUM("totalPrice"), 0) AS revenue FROM public."orders" WHERE "createdAt" IS NOT NULL GROUP BY DATE("createdAt") ORDER BY day DESC LIMIT 7')
                rows = await cur.fetchall()
                snapshot["daily_revenue"] = [float(row[1] or 0) for row in rows]
        except Exception:
            snapshot["daily_revenue"] = []

        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    'SELECT mi."name", COALESCE(SUM(oi.quantity), 0) AS qty FROM public."order_items" oi JOIN public."menu_items" mi ON mi.id = oi."menuItemId" GROUP BY mi."name" ORDER BY qty DESC LIMIT 5'
                )
                rows = await cur.fetchall()
                snapshot["popular_items"] = [{"name": row[0], "qty": int(row[1] or 0)} for row in rows]
        except Exception:
            snapshot["popular_items"] = []

        try:
            async with conn.cursor() as cur:
                await cur.execute('SELECT COUNT(*) FROM public."staff"')
                row = await cur.fetchone()
                if row:
                    snapshot["staff_count"] = int(row[0] or 0)
                await cur.execute('SELECT COUNT(*) FROM public."loyalty_accounts"')
                row = await cur.fetchone()
                if row:
                    snapshot["loyalty_accounts"] = int(row[0] or 0)
        except Exception:
            snapshot["staff_count"] = 0
            snapshot["loyalty_accounts"] = 0

        snapshot["has_data"] = (
            snapshot["menu_items"] > 0
            and snapshot["orders"] > 0
            and (snapshot["recent_revenue_30d"] > 0 or snapshot["recent_orders_30d"] > 0)
        )
        return snapshot

    @staticmethod
    async def get_order_rows(conn: Optional[AsyncConnection], limit: int = 30) -> List[Dict[str, Any]]:
        if conn is None:
            return []
        queries = [
            'SELECT * FROM public."orders" ORDER BY "createdAt" DESC LIMIT %s',
            'SELECT * FROM public."order_items" ORDER BY "id" DESC LIMIT %s',
        ]
        for sql in queries:
            try:
                async with conn.cursor() as cur:
                    await cur.execute(sql, (limit,))
                    rows = await cur.fetchall()
                    if rows:
                        return [dict(row) for row in rows]
            except Exception:
                continue
        return []
