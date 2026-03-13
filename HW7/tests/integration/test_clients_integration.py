import pytest
import pytest_asyncio
import os
import asyncpg
import redis.asyncio as aioredis
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer
from testcontainers.kafka import KafkaContainer

from clients.postgres import init_pg_pool, close_pg_pool, get_pg_connection
from clients.redis import init_redis, close_redis, get_redis_connection
from clients.kafka import ModerationProducer

pytestmark = pytest.mark.integration

@pytest_asyncio.fixture(scope="module")
async def postgres_container():
    with PostgresContainer("postgres:15") as pg:
        yield pg

@pytest_asyncio.fixture(scope="module")
async def redis_container():
    with RedisContainer("redis:7") as redis:
        yield redis

@pytest_asyncio.fixture(scope="module")
async def kafka_container():
    with KafkaContainer("confluentinc/cp-kafka:7.3.0") as kafka:
        yield kafka

@pytest_asyncio.fixture(autouse=True)
async def setup_pg(postgres_container):
    os.environ["DB_HOST"] = postgres_container.get_container_host_ip()
    os.environ["DB_PORT"] = postgres_container.get_exposed_port(5432)
    os.environ["DB_USER"] = postgres_container.username
    os.environ["DB_PASSWORD"] = postgres_container.password
    os.environ["DB_NAME"] = postgres_container.dbname
    await init_pg_pool()
    yield
    await close_pg_pool()

@pytest_asyncio.fixture(autouse=True)
async def setup_redis(redis_container):
    os.environ["REDIS_HOST"] = redis_container.get_container_host_ip()
    os.environ["REDIS_PORT"] = redis_container.get_exposed_port(6379)
    await init_redis()
    yield
    await close_redis()

@pytest.mark.asyncio
class TestPostgresClient:
    @pytest.mark.parametrize("query", ["SELECT 1", "SELECT 'test'"])
    async def test_connection_and_query(self, query):
        async with get_pg_connection() as conn:
            result = await conn.fetchval(query)
            assert result is not None

    @pytest.mark.parametrize("table_name", ["users", "advertisements"])
    async def test_table_exists(self, table_name):
        async with get_pg_connection() as conn:
            result = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = $1)",
                table_name
            )
            assert result is True

@pytest.mark.asyncio
class TestRedisClient:
    @pytest.mark.parametrize("key,value", [("foo", "bar"), ("num", 123)])
    async def test_set_get(self, key, value):
        async with get_redis_connection() as r:
            await r.set(key, value)
            result = await r.get(key)
            assert result == str(value)

    @pytest.mark.parametrize("key", ["temp"])
    async def test_delete(self, key):
        async with get_redis_connection() as r:
            await r.set(key, "val")
            await r.delete(key)
            result = await r.get(key)
            assert result is None

@pytest.mark.asyncio
class TestKafkaClient:
    @pytest.mark.parametrize("topic,message", [
        ("test_topic", {"key": "value"}),
        ("moderation", {"moderation_id": 1, "item_id": 10}),
    ])
    async def test_producer_send(self, kafka_container, topic, message):
        os.environ["KAFKA_BOOTSTRAP"] = kafka_container.get_bootstrap_server()
        producer = ModerationProducer()
        await producer.start()
        try:
            await producer.send_message(topic, message)
            assert True
        finally:
            await producer.stop()