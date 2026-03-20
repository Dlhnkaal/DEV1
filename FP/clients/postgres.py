import asyncpg
from typing import AsyncGenerator
import os
from dotenv import load_dotenv 

from contextlib import asynccontextmanager

load_dotenv()

pg_pool: asyncpg.Pool | None = None

async def init_pg_pool():
    global pg_pool
    pg_pool = await asyncpg.create_pool(
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "123456"),
        database=os.getenv("DB_NAME", "advertisement_db"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432"))
    )

async def close_pg_pool():
    global pg_pool
    if pg_pool:
        await pg_pool.close()

@asynccontextmanager
async def get_pg_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    if pg_pool is None:
        raise RuntimeError("Database pool is not initialized")
        
    async with pg_pool.acquire() as connection:
        yield connection