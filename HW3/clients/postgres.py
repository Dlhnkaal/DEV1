import asyncpg
from typing import AsyncGenerator
from contextlib import asynccontextmanager
import os

@asynccontextmanager
async def get_pg_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    connection: asyncpg.Connection = await asyncpg.connect(
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "123456"),
        database=os.getenv("DB_NAME", "advertisement_db"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")))

    try:
        yield connection
    finally:
        await connection.close()