import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        database.pool = None

    def test_db_fetch_one_initializes_pool_if_missing(self):
        async def run_test():
            fake_pool = AsyncMock()
            fake_conn = AsyncMock()
            fake_pool.acquire.return_value.__aenter__.return_value = fake_conn
            fake_conn.fetchrow.return_value = {"telegram_id": 1}

            with patch("database.asyncpg.create_pool", new=AsyncMock(return_value=fake_pool)) as create_pool:
                row = await database.db_fetch_one("SELECT 1")

            self.assertEqual(row, {"telegram_id": 1})
            create_pool.assert_awaited_once_with(database.DATABASE_URL)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
