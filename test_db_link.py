import asyncio
import asyncpg

DB_CONFIG = {
    "host": "localhost",
    "user": "postgres",
    "password": "Alpha.com002",
    "database": "unical_bot"
}

async def test_connection():
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        print("✅ SUCCESS: Bot is linked to PostgreSQL!")
        await conn.close()
    except Exception as e:
        print(f"❌ FAILED: Could not link. Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())