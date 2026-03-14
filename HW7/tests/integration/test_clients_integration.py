import os
import pytest
import pytest_asyncio
import asyncpg
import redis.asyncio as aioredis
from clients.postgres import get_pg_connection
from clients.redis import get_redis_connection
from clients.kafka import ModerationProducer


pytestmark = pytest.mark.integration


@pytest.mark.asyncio(loop_scope="session")
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


@pytest.mark.asyncio(loop_scope="session")
class TestRedisClient:
    @pytest.mark.parametrize("key,value", [("foo", "bar"), ("num", "123")])
    async def test_set_get(self, key, value):
        async with get_redis_connection() as r:
            await r.set(key, value)
            result = await r.get(key)
            assert result == value

    @pytest.mark.parametrize("key", ["temp"])
    async def test_delete(self, key):
        async with get_redis_connection() as r:
            await r.set(key, "val")
            await r.delete(key)
            result = await r.get(key)
            assert result is None


@pytest.mark.asyncio(loop_scope="session")
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
