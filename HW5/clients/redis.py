import os
import redis.asyncio as redis
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

@asynccontextmanager
async def get_redis_connection() -> AsyncGenerator[redis.Redis, None]:
    """
    Контекстный менеджер для получения подключения к Redis.
    Параметры берутся из переменных окружения.
    """
    connection = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        password=os.getenv("REDIS_PASSWORD", None),
        db=int(os.getenv("REDIS_DB", 0)),
        decode_responses=True,          # для автоматической декодировки строк
        socket_connect_timeout=5,
        socket_timeout=5,
        health_check_interval=30,
    )
    try:
        await connection.ping()  # проверка доступности
        yield connection
    finally:
        await connection.aclose()