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

SAMPLE_DISHES = [
    {
        "name": "Spicy Paneer Tikka Wrap",
        "description": "Grilled marinated cottage cheese wrapped with melted cheese, mint chutney, bell peppers, and chipotle mayo.",
        "category": "Wraps",
        "price": 14.50,
        "is_vegetarian": True,
        "image_url": "https://images.unsplash.com/photo-1626777552726-4a6b54c97e46",
    },
    {
        "name": "Truffle Forest Mushroom Risotto",
        "description": "Creamy Italian Arborio rice cooked slow with wild forest mushrooms, white truffle oil, and aged parmesan cheese.",
        "category": "Mains",
        "price": 19.99,
        "is_vegetarian": True,
        "image_url": "https://images.unsplash.com/photo-1633964913295-ceb43826e7c9",
    },
    {
        "name": "Smoked Wagyu Bacon Burger",
        "description": "Juicy Wagyu beef patty topped with crispy bacon, smoked cheddar, caramelized onions, and house barbecue mayo.",
        "category": "Burgers",
        "price": 22.50,
        "is_vegetarian": False,
        "image_url": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd",
    },
    {
        "name": "Artisanal Ethiopian Cold Brew Coffee",
        "description": "Single-origin Ethiopian Yirgacheffe cold brew coffee steeped for 24 hours with dark chocolate and berry notes.",
        "category": "Beverages",
        "price": 5.99,
        "is_vegetarian": True,
        "image_url": "https://images.unsplash.com/photo-1517701604599-bb29b565090c",
    },
    {
        "name": "Matcha Green Tea Latte",
        "description": "Ceremonial grade Japanese Uji matcha steamed with oat milk and drizzled with organic wildflower honey.",
        "category": "Beverages",
        "price": 6.50,
        "is_vegetarian": True,
        "image_url": "https://images.unsplash.com/photo-1536256263959-770b48d82b0a",
    },
    {
        "name": "Fiery Crispy Chicken Tenders",
        "description": "Hand-breaded double fried chicken tenders tossed in habanero honey glaze, served with ranch dressing.",
        "category": "Starters",
        "price": 13.99,
        "is_vegetarian": False,
        "image_url": "https://images.unsplash.com/photo-1562967914-608f82629710",
    },
    {
        "name": "Avocado Citrus Quinoa Bowl",
        "description": "Fresh Hass avocado, tri-color quinoa, baby spinach, orange segments, toasted pumpkin seeds, and citrus vinaigrette.",
        "category": "Salads",
        "price": 15.25,
        "is_vegetarian": True,
        "image_url": "https://images.unsplash.com/photo-1540420773420-3366772f4999",
    },
    {
        "name": "Wood-Fired Margherita Pizza",
        "description": "Authentic San Marzano tomato sauce, fresh buffalo mozzarella, fresh basil leaves, and extra virgin olive oil.",
        "category": "Pizza",
        "price": 17.00,
        "is_vegetarian": True,
        "image_url": "https://images.unsplash.com/photo-1604382354936-07c5d9983bd3",
    },
    {
        "name": "Seared Atlantic Salmon Fillet",
        "description": "Pan-seared wild Atlantic salmon served over asparagus spears, lemon dill butter sauce, and roasted garlic potatoes.",
        "category": "Mains",
        "price": 26.50,
        "is_vegetarian": False,
        "image_url": "https://images.unsplash.com/photo-1467003909585-2f8a72700288",
    },
    {
        "name": "Double Dark Chocolate Lava Cake",
        "description": "Warm molten chocolate cake with gooey dark Belgian chocolate center, served with Madagascar vanilla bean ice cream.",
        "category": "Desserts",
        "price": 9.50,
        "is_vegetarian": True,
        "image_url": "https://images.unsplash.com/photo-1606313564200-e75d5e30476c",
    },
]


async def seed_database() -> None:
    """
    Connects to Neon DB, initializes table schema with pgvector, and inserts sample items.
    """
    logger.info("Initializing Neon DB schema & seeding sample menu items...")
    embedder = TextEmbedder.get_instance()

    try:
        async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL) as conn:
            async with conn.cursor() as cur:
                # 1. Enable pgvector extension
                logger.info("Ensuring pgvector extension is enabled...")
                await cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

                # 2. Create menu_items table schema if not existing
                logger.info("Creating or altering 'menu_items' table structure...")
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS menu_items (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        description TEXT NOT NULL,
                        category VARCHAR(100),
                        price NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
                        is_vegetarian BOOLEAN NOT NULL DEFAULT FALSE,
                        image_url TEXT,
                        embedding vector(384),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)

                # 3. Add any missing columns if table existed previously
                await cur.execute("""
                    ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS category VARCHAR(100);
                    ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS price NUMERIC(10, 2) DEFAULT 0.0;
                    ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS is_vegetarian BOOLEAN DEFAULT FALSE;
                    ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS image_url TEXT;
                    ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS embedding vector(384);
                """)

                # 4. Remove NOT NULL constraint on legacy categoryId column if present
                await cur.execute("""
                    DO $$ 
                    BEGIN 
                        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='menu_items' AND column_name='categoryId') THEN 
                            ALTER TABLE menu_items ALTER COLUMN "categoryId" DROP NOT NULL;
                        END IF;
                    END $$;
                """)

                # 5. Create HNSW vector index for similarity queries
                await cur.execute("""
                    CREATE INDEX IF NOT EXISTS menu_items_embedding_hnsw_idx 
                    ON menu_items USING hnsw (embedding vector_l2_ops);
                """)
                await conn.commit()

                # 6. Insert or update sample menu items
                logger.info(f"Seeding {len(SAMPLE_DISHES)} menu items into Neon database...")
                for item in SAMPLE_DISHES:
                    # Generate 384-dimensional vector embedding for item description
                    vec = embedder.encode_text(item["description"])
                    vec_str = f"[{','.join(map(str, vec))}]"

                    # Check if item already exists by name
                    await cur.execute(
                        "SELECT id FROM menu_items WHERE name = %s LIMIT 1;", [item["name"]]
                    )
                    existing = await cur.fetchone()

                    if existing:
                        item_id = existing[0]
                        await cur.execute(
                            """
                            UPDATE menu_items
                            SET description = %s, category = %s, price = %s, 
                                is_vegetarian = %s, image_url = %s, embedding = %s::vector,
                                updated_at = NOW()
                            WHERE id = %s;
                            """,
                            [
                                item["description"],
                                item["category"],
                                item["price"],
                                item["is_vegetarian"],
                                item["image_url"],
                                vec_str,
                                item_id,
                            ],
                        )
                    else:
                        await cur.execute(
                            """
                            INSERT INTO menu_items (name, description, category, price, is_vegetarian, image_url, embedding)
                            VALUES (%s, %s, %s, %s, %s, %s, %s::vector);
                            """,
                            [
                                item["name"],
                                item["description"],
                                item["category"],
                                item["price"],
                                item["is_vegetarian"],
                                item["image_url"],
                                vec_str,
                            ],
                        )

                await conn.commit()
                logger.info("Database seeding completed successfully on Neon PostgreSQL!")

    except Exception as e:
        logger.error(f"Error seeding database: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(seed_database())
