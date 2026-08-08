import asyncio
import sys
import psycopg

# Fix Windows ProactorEventLoop compatibility for psycopg async mode
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.config import settings
from app.core.logger import logger


async def init_user_tracking() -> None:
    """
    Creates the user behavior tracking, order history, and preference
    profile tables required for personalized AI recommendations.
    Safe to run multiple times (CREATE TABLE IF NOT EXISTS).
    """
    logger.info("Starting user tracking schema initialization...")

    async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            # 1. user_events - behavior tracking (view, like, favorite, add_to_cart, click)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS user_events (
                    id BIGSERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    menu_item_id BIGINT REFERENCES menu_items(id),
                    event_type VARCHAR(50) NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_user_events_user
                    ON user_events (user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_user_events_item
                    ON user_events (menu_item_id);
            """)

            # 2. user_orders - order history
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS user_orders (
                    id BIGSERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    total NUMERIC(10, 2) DEFAULT 0.0,
                    status VARCHAR(50) DEFAULT 'completed',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_user_orders_user
                    ON user_orders (user_id, created_at DESC);
            """)

            # 3. user_order_items - items within an order
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS user_order_items (
                    id BIGSERIAL PRIMARY KEY,
                    order_id BIGINT NOT NULL REFERENCES user_orders(id) ON DELETE CASCADE,
                    menu_item_id BIGINT REFERENCES menu_items(id),
                    quantity INT DEFAULT 1,
                    price NUMERIC(10, 2) DEFAULT 0.0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_user_order_items_order
                    ON user_order_items (order_id);
                CREATE INDEX IF NOT EXISTS idx_user_order_items_item
                    ON user_order_items (menu_item_id);
            """)

            # 4. user_preference_profile - aggregated preference vector per user
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS user_preference_profile (
                    user_id VARCHAR(255) PRIMARY KEY,
                    preference_vector vector(384),
                    favorite_categories JSONB,
                    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)

            await conn.commit()
            logger.info("User tracking schema initialized successfully!")


if __name__ == "__main__":
    asyncio.run(init_user_tracking())
