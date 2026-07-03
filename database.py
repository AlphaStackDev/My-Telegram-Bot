import asyncpg
import logging

# Configuration
DB_CONFIG = {
    "user": "postgres",
    "password": "Alpha.com002",
    "database": "unical_bot",
    "host": "localhost",
}

# Global pool variable
pool = None

async def init_db():
    """Initializes the connection pool. Call this once at bot startup."""
    global pool
    try:
        pool = await asyncpg.create_pool(**DB_CONFIG)
        logging.info("Database connection pool created successfully.")
    except Exception as e:
        logging.error(f"Failed to create database pool: {e}")
        raise e

async def db_execute(query: str, params: tuple = ()):
    """Executes a query (INSERT, UPDATE, DELETE)."""
    async with pool.acquire() as conn:
        return await conn.execute(query, *params)

async def db_fetch_all(query: str, params: tuple = ()):
    """Fetches all rows as a list of dictionaries."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]

async def db_fetch_one(query: str, params: tuple = ()):
    """Fetches a single row as a dictionary."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
        return dict(row) if row else None

async def close_db():
    """Closes the pool when the bot shuts down."""
    if pool:
        await pool.close()