import pytest
import asyncio
import os
from unittest.mock import patch, AsyncMock

from workers.moderation_worker import ModerationWorker
from repositories.moderation import ModerationRepository

pytestmark = pytest.mark.integration


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.usefixtures("run_migrations", "clean_db")
async def test_worker_processes_message(kafka_container, sample_user_and_ad):
    user, ad = sample_user_and_ad
    item_id = ad.id

    mod_repo = ModerationRepository()
    pending = await mod_repo.create_pending(item_id)

    worker = ModerationWorker()

    unique_group = f"test_worker_group_{pending.id}"

    with patch("workers.moderation_worker.init_pg_pool", new=AsyncMock()), \
         patch("workers.moderation_worker.close_pg_pool", new=AsyncMock()):

        original_start = worker.start

        async def patched_start():
            from clients.postgres import init_pg_pool as _pg
            from clients.redis import init_redis as _redis
            worker.ml_service._load_model()

            from aiokafka import AIOKafkaConsumer
            import json
            worker.consumer = AIOKafkaConsumer(
                "moderation",
                bootstrap_servers=worker._bootstrap,
                group_id=unique_group,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                auto_offset_reset="earliest",
                enable_auto_commit=False,
            )
            await worker.consumer.start()
            await worker.dlq_producer.start()

        worker.start = patched_start

        task = asyncio.create_task(worker.consume())
        await asyncio.sleep(3)

        from clients.kafka import ModerationProducer
        producer = ModerationProducer()
        await producer.start()
        await producer.send_moderation_request(pending.id, item_id)
        await producer.stop()

        await asyncio.sleep(7)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await mod_repo.delete_cache(pending.id)
    updated = await mod_repo.get_result_by_id(pending.id)
    assert updated.status in ("completed", "failed")
    if updated.status == "completed":
        assert updated.is_violation is not None
        assert updated.probability is not None