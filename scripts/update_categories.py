import asyncio
import sys
import psycopg
from psycopg.rows import dict_row

# Fix Windows ProactorEventLoop compatibility for psycopg async mode
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.config import settings
from app.core.logger import logger

# Mapping of existing generic category names -> new dish-specific category names.
# Adjust this mapping to match your desired categories.
CATEGORY_RENAMES = {
    "Veg": "Veg MoMo",
    "Chicken": "Chicken MoMo",
    # Add any other renames here, e.g.:
    # "Tea": "Tea",
    # "Summer Drink": "Summer Drink",
}


async def update_categories() -> None:
    """
    Renames categories in the relational 'categories' table to dish-specific names
    so their values appear as 'Veg MoMo', 'Chicken MoMo', etc. in API responses.
    """
    logger.info("Starting category rename migration...")

    async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL) as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            # Confirm the categories table exists
            await cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'categories';
            """)
            columns = [row["column_name"] for row in await cur.fetchall()]
            logger.info(f"Found columns in 'categories' table: {columns}")

            if "name" not in columns:
                logger.error(
                    "'categories' table does not have a 'name' column. "
                    "Please verify your database schema."
                )
                sys.exit(1)

            for old_name, new_name in CATEGORY_RENAMES.items():
                await cur.execute(
                    "UPDATE categories SET name = %s WHERE name = %s;",
                    [new_name, old_name],
                )
                logger.info(
                    f"Renamed category '{old_name}' -> '{new_name}' "
                    f"({cur.rowcount} row(s) affected)."
                )

            await conn.commit()
            logger.info("Category rename migration completed successfully!")

            # Show the resulting categories for verification
            await cur.execute("SELECT id, name FROM categories ORDER BY name;")
            for row in await cur.fetchall():
                print(f"  {row['id']} | {row['name']}")


if __name__ == "__main__":
    asyncio.run(update_categories())

