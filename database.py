import os
import asyncpg
import logging

# We fetch the URL from the environment (Render's Environment Variables)
# If not found, it defaults to a local development string
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:Alpha.com002@localhost:5432/unical_bot")

pool = None

async def init_db():
    """Initializes the connection pool using the DATABASE_URL."""
    global pool
    try:
        # asyncpg handles the connection string directly
        pool = await asyncpg.create_pool(DATABASE_URL)
        logging.info("Database connection pool created successfully.")
    except Exception as e:
        logging.error(f"Failed to create database pool: {e}")
        raise e

# The rest of your functions remain exactly the same
async def db_execute(query: str, params: tuple = ()):
    async with pool.acquire() as conn:
        return await conn.execute(query, *params)

async def db_fetch_all(query: str, params: tuple = ()):
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]

async def db_fetch_one(query: str, params: tuple = ()):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
        return dict(row) if row else None

async def close_db():
    if pool:
        await pool.close()