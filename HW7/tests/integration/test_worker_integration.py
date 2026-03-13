import pytest
import pytest_asyncio
import asyncio
import os
from testcontainers.kafka import KafkaContainer
from workers.moderation_worker import ModerationWorker
from repositories.moderation import ModerationRepository
from models.moderation import AsyncPredictRequest

pytestmark = pytest.mark.integration

@pytest_asyncio.fixture(scope="module")
async def kafka_container():
    with KafkaContainer("confluentinc/cp-kafka:7.3.0") as kafka:
        os.environ["KAFKA_BOOTSTRAP"] = kafka.get_bootstrap_server()
        yield kafka

@pytest_asyncio.fixture(autouse=True)
async def setup_postgres(postgres_container):
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

@pytest_asyncio.fixture
async def sample_user_and_ad(clean_db):
    from repositories.user import UserRepository
    from repositories.advertisement import AdvertisementRepository
    user_repo = UserRepository()
    user = await user_repo.create("seller", "pass", "s@ex.com", True)
    ad_repo = AdvertisementRepository()
    ad = await ad_repo.create(user.id, "Ad", "Desc", 1, 2)
    return user, ad

@pytest.mark.asyncio
async def test_worker_processes_message(kafka_container, sample_user_and_ad, redis_container):
    user, ad = sample_user_and_ad
    item_id = ad.id

    mod_repo = ModerationRepository()
    pending = await mod_repo.create_pending(item_id)

    worker = ModerationWorker()
    task = asyncio.create_task(worker.consume())

    await asyncio.sleep(2)

    from clients.kafka import ModerationProducer
    producer = ModerationProducer()
    await producer.start()
    await producer.send_moderation_request(pending.id, item_id)
    await producer.stop()

    await asyncio.sleep(5)

    updated = await mod_repo.get_result_by_id(pending.id)
    assert updated.status == "completed"  
    if updated.status == "completed":
        assert updated.is_violation is not None
        assert updated.probability is not None

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await worker.stop()