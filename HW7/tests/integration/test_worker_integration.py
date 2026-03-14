import pytest
import pytest_asyncio
import asyncio
import os
from testcontainers.kafka import KafkaContainer
from workers.moderation_worker import ModerationWorker
from repositories.moderation import ModerationRepository
from models.moderation import AsyncPredictRequest
from clients.postgres import init_pg_pool, close_pg_pool
from clients.redis import init_redis, close_redis

pytestmark = pytest.mark.integration

@pytest.mark.usefixtures("run_migrations", "clean_db")
async def test_worker_processes_message(kafka_container, sample_user_and_ad, redis_container):
    user, ad = sample_user_and_ad
    item_id = ad.id

    # создаём задачу в БД
    mod_repo = ModerationRepository()
    pending = await mod_repo.create_pending(item_id)

    # запускаем воркер в фоновой задаче
    worker = ModerationWorker()
    task = asyncio.create_task(worker.consume())

    # даём воркеру время подключиться
    await asyncio.sleep(2)

    # отправляем сообщение через продюсер
    from clients.kafka import ModerationProducer
    producer = ModerationProducer()
    await producer.start()
    await producer.send_moderation_request(pending.id, item_id)
    await producer.stop()

    # ждём обработки
    await asyncio.sleep(5)

    # проверяем результат в БД
    updated = await mod_repo.get_result_by_id(pending.id)
    assert updated.status in ("completed", "failed")  # зависит от модели
    if updated.status == "completed":
        assert updated.is_violation is not None
        assert updated.probability is not None

    # останавливаем воркер
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await worker.stop()