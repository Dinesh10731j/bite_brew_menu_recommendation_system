import asyncio
import sys
import psycopg
from psycopg.rows import dict_row

# Fix Windows ProactorEventLoop compatibility for psycopg async mode
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.config import settings
from app.core.logger import logger
from app.models.embedder import TextEmbedder


async def sync_missing_embeddings() -> None:
    """
    Scans Neon DB for menu items where embedding IS NULL, generates 384-length vector
    embeddings using TextEmbedder, and batch updates the database records.
    """
    logger.info("Starting batch synchronization of missing vector embeddings...")
    embedder = TextEmbedder.get_instance()

    try:
        async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL) as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                # 1. Query all items with NULL embedding
                await cur.execute("""
                    SELECT id, name, description 
                    FROM menu_items 
                    WHERE embedding IS NULL;
                """)
                missing_items = await cur.fetchall()

                if not missing_items:
                    logger.info("No menu items found missing vector embeddings. Database is up to date!")
                    return

                logger.info(f"Found {len(missing_items)} menu items requiring vector embeddings.")

                # 2. Batch encode descriptions
                descriptions = [item["description"] for item in missing_items]
                embeddings = embedder.encode_batch(descriptions)

                # 3. Batch update DB records safely without assuming updated_at exists
                updated_count = 0
                for item, vector in zip(missing_items, embeddings):
                    vector_str = f"[{','.join(map(str, vector))}]"
                    await cur.execute(
                        """
                        UPDATE menu_items
                        SET embedding = %s::vector
                        WHERE id = %s;
                        """,
                        [vector_str, item["id"]],
                    )
                    updated_count += 1

                await conn.commit()
                logger.info(
                    f"Successfully synchronized {updated_count} vector embeddings in Neon PostgreSQL!"
                )

    except Exception as e:
        logger.error(f"Error during vector embedding sync: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(sync_missing_embeddings())
