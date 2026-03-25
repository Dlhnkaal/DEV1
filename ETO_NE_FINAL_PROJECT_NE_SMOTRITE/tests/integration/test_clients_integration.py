import asyncio
import os
import time
import pytest
import pytest_asyncio
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

    @pytest.mark.parametrize("table_name", [
        "users",
        "advertisements",
        "moderation_results",
        "account",
    ])
    async def test_table_exists(self, table_name):
        async with get_pg_connection() as conn:
            result = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM information_schema.tables "
                "WHERE table_name = $1)",
                table_name
            )
            assert result is True, f"Table '{table_name}' not found"

    @pytest.mark.parametrize("index_name", [
        "idx_advertisements_seller_id_category",
        "idx_advertisements_is_closed",
    ])
    async def test_index_exists(self, index_name):
        async with get_pg_connection() as conn:
            result = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM pg_indexes WHERE indexname = $1)",
                index_name
            )
            assert result is True, f"Index '{index_name}' not found"

    async def test_updated_at_trigger(self, clean_db):
        unique = f"trigger_test_{int(time.time() * 1000)}"
        async with get_pg_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO users (login, password, email, is_verified_seller)
                VALUES ($1, 'pass', $2, false)
                RETURNING id, updated_at
                """,
                unique, f"{unique}@test.com"
            )
            user_id = row["id"]
            original_updated_at = row["updated_at"]

            await asyncio.sleep(0.01)

            new_row = await conn.fetchrow(
                "UPDATE users SET login = $1 WHERE id = $2 RETURNING updated_at",
                f"{unique}_upd", user_id
            )
            assert new_row["updated_at"] >= original_updated_at

            await conn.execute("DELETE FROM users WHERE id = $1", user_id)

    async def test_foreign_key_cascade_delete(self, clean_db):
        unique = f"cascade_{int(time.time() * 1000)}"
        user_id = None

        async with get_pg_connection() as conn:
            try:
                user = await conn.fetchrow(
                    """INSERT INTO users (login, password, email, is_verified_seller)
                       VALUES ($1, 'pass', $2, false)
                       RETURNING id""",
                    unique, f"{unique}@test.com"
                )
                user_id = user["id"]

                ad = await conn.fetchrow(
                    """INSERT INTO advertisements
                       (seller_id, name, description, category, images_qty)
                       VALUES ($1, 'Ad', 'Desc', 1, 1) RETURNING id""",
                    user_id
                )
                ad_id = ad["id"]

                await conn.execute(
                    "INSERT INTO moderation_results (item_id, status) VALUES ($1, 'pending')",
                    ad_id
                )

                await conn.execute("DELETE FROM users WHERE id = $1", user_id)
                user_id = None

                ad_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM advertisements WHERE id = $1", ad_id
                )
                mod_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM moderation_results WHERE item_id = $1", ad_id
                )

                assert ad_count == 0, "Advertisement should be deleted by CASCADE"
                assert mod_count == 0, "Moderation result should be deleted by CASCADE"

            finally:
                if user_id is not None:
                    await conn.execute("DELETE FROM users WHERE id = $1", user_id)


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

    async def test_ttl_expiry(self):
        async with get_redis_connection() as r:
            await r.setex("ttl_test_key", 1, "expires_soon")
            assert await r.get("ttl_test_key") == "expires_soon"
            await asyncio.sleep(1.2)
            assert await r.get("ttl_test_key") is None

    async def test_ttl_value_is_set(self):
        async with get_redis_connection() as r:
            await r.setex("ttl_check_key", 60, "value")
            ttl = await r.ttl("ttl_check_key")
            assert ttl > 0
            await r.delete("ttl_check_key")

    async def test_pipeline_atomic_set(self):
        async with get_redis_connection() as r:
            pipe = r.pipeline()
            pipe.set("pipe_key_1", "val1")
            pipe.set("pipe_key_2", "val2")
            await pipe.execute()

            assert await r.get("pipe_key_1") == "val1"
            assert await r.get("pipe_key_2") == "val2"

            await r.delete("pipe_key_1", "pipe_key_2")

    async def test_key_does_not_exist_returns_none(self):
        async with get_redis_connection() as r:
            result = await r.get("definitely_nonexistent_key_xyz_987")
            assert result is None

    async def test_overwrite_existing_key(self):
        async with get_redis_connection() as r:
            await r.set("overwrite_key", "original")
            await r.set("overwrite_key", "updated")
            result = await r.get("overwrite_key")
            assert result == "updated"
            await r.delete("overwrite_key")


@pytest.mark.asyncio(loop_scope="session")
class TestKafkaClient:

    @pytest.mark.parametrize("topic,message", [
        ("test_topic", {"key": "value"}),
        ("moderation", {"moderation_id": 1, "item_id": 10}),
        ("moderation_dlq", {"original_message": {}, "error": "test", "retry_count": 3}),
    ])
    async def test_producer_send(self, topic, message):
        producer = ModerationProducer()
        await producer.start()
        try:
            await producer.send_message(topic, message)
        finally:
            await producer.stop()

    async def test_send_moderation_request_format(self):
        from aiokafka import AIOKafkaConsumer
        import json

        bootstrap = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
        group_id = f"test_format_check_{int(time.time())}"

        consumer = AIOKafkaConsumer(
            "moderation",
            bootstrap_servers=bootstrap,
            group_id=group_id,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="latest",
            enable_auto_commit=True,
            consumer_timeout_ms=5000,
        )
        await consumer.start()

        producer = ModerationProducer()
        await producer.start()
        await producer.send_moderation_request(moderation_id=42, item_id=7)
        await producer.stop()

        received = []

        async def _consume():
            async for msg in consumer:
                received.append(msg.value)
                if msg.value.get("moderation_id") == 42 and msg.value.get("item_id") == 7:
                    break

        try:
            await asyncio.wait_for(_consume(), timeout=10.0)
        except asyncio.TimeoutError:
            pass
        finally:
            await consumer.stop()

        matching = [
            m for m in received
            if m.get("moderation_id") == 42 and m.get("item_id") == 7
        ]
        assert len(matching) >= 1, "Message with moderation_id=42 not found"
        assert "timestamp" in matching[0], "Message must contain 'timestamp' field"

    async def test_producer_sends_to_dlq_topic(self):
        producer = ModerationProducer()
        await producer.start()
        try:
            dlq_message = {
                "original_message": {"moderation_id": 99, "item_id": 5},
                "error": "Test DLQ error",
                "timestamp": "2024-01-01T00:00:00",
                "retry_count": 3,
            }
            await producer.send_message("moderation_dlq", dlq_message)
        finally:
            await producer.stop()