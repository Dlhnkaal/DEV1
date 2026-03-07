import os
import redis.asyncio as aioredis
from typing import AsyncGenerator
from dotenv import load_dotenv

from contextlib import asynccontextmanager


load_dotenv()

redis_client: aioredis.Redis | None = None

async def init_redis():
    global redis_client
    redis_client = aioredis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        password=os.getenv("REDIS_PASSWORD", None),
        db=int(os.getenv("REDIS_DB", 0)),
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        health_check_interval=30,
    )

async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.aclose()

@asynccontextmanager
async def get_redis_connection() -> AsyncGenerator[aioredis.Redis, None]:
    if redis_client is None:
        raise RuntimeError("Redis is not initialized")
    yield redis_client