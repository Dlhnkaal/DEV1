import os
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from main import app as real_app
from dependencies import get_current_account
from models.account import AccountModel
from clients.postgres import init_pg_pool, close_pg_pool, get_pg_connection
from clients.redis import init_redis, close_redis

_LOCAL_DB_URL = "postgresql://postgres:123456@localhost:5435/advertisement_db"


def _check_infra_available() -> str | None:
    import socket

    checks = [
        ("localhost", 5435, "PostgreSQL"),
        ("localhost", 6379, "Redis"),
        ("localhost", 9092, "Kafka"),
    ]
    missing = []
    for host, port, name in checks:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            if s.connect_ex((host, port)) != 0:
                missing.append(f"{name} ({host}:{port})")

    if missing:
        return f"Infrastructure unavailable: {', '.join(missing)}"
    return None


@pytest_asyncio.fixture(scope="session", autouse=True)
async def initialize_clients():
    reason = _check_infra_available()
    if reason:
        pytest.skip(reason)

    os.environ["DB_HOST"] = "localhost"
    os.environ["DB_PORT"] = "5435"
    os.environ["REDIS_HOST"] = "localhost"
    os.environ["REDIS_PORT"] = "6379"
    os.environ["KAFKA_BOOTSTRAP"] = "localhost:9092"

    try:
        await init_pg_pool()
    except Exception as e:
        pytest.skip(f"Failed to connect to PostgreSQL: {e}")

    try:
        await init_redis()
    except Exception as e:
        await close_pg_pool()
        pytest.skip(f"Failed to connect to Redis: {e}")

    yield

    await close_pg_pool()
    await close_redis()


@pytest_asyncio.fixture(scope="session")
async def run_migrations(initialize_clients):
    import subprocess
    import sys
    import pathlib

    project_root = pathlib.Path(__file__).parent.parent.parent

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=project_root,
        env={**os.environ, "DATABASE_URL": _LOCAL_DB_URL},
    )
    yield


@pytest_asyncio.fixture
async def clean_db(initialize_clients, run_migrations):
    async with get_pg_connection() as conn:
        await conn.execute(
            "TRUNCATE moderation_results, advertisements, users, account "
            "RESTART IDENTITY CASCADE"
        )
    from clients.redis import redis_client
    if redis_client is not None:
        await redis_client.flushdb()
    yield
    async with get_pg_connection() as conn:
        await conn.execute(
            "TRUNCATE moderation_results, advertisements, users, account "
            "RESTART IDENTITY CASCADE"
        )
    from clients.redis import redis_client
    if redis_client is not None:
        await redis_client.flushdb()


class _KafkaContainerShim:
    def get_bootstrap_server(self) -> str:
        return os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")


@pytest.fixture(scope="session")
def kafka_container():
    return _KafkaContainerShim()


class _RedisContainerShim:
    def get_connection_url(self) -> str:
        host = os.getenv("REDIS_HOST", "localhost")
        port = os.getenv("REDIS_PORT", "6379")
        return f"redis://{host}:{port}"


@pytest.fixture(scope="session")
def redis_container():
    return _RedisContainerShim()


@pytest_asyncio.fixture
async def sample_user_and_ad(clean_db):
    from repositories.user import UserRepository
    from repositories.advertisement import AdvertisementRepository

    user_repo = UserRepository()
    user = await user_repo.create("worker_seller", "pass1234", "worker@ex.com", True)
    ad_repo = AdvertisementRepository()
    ad = await ad_repo.create(user.id, "Worker Ad", "Desc for worker", 1, 2)
    return user, ad


@pytest.fixture
def mock_account() -> AccountModel:
    return AccountModel(id=1, login="test_user", password="hashedpass123", is_blocked=False)


@pytest.fixture
def mock_current_account(mock_account) -> Generator:
    with patch("dependencies.get_current_account") as mock:
        mock.return_value = mock_account
        yield mock


@pytest.fixture
def app() -> FastAPI:
    return real_app


@pytest_asyncio.fixture
async def async_client(app: FastAPI, initialize_clients) -> AsyncGenerator:
    transport = ASGITransport(app=app)

    from services.advertisement import AdvertisementMLService
    from services.moderation import AsyncModerationService
    from models.advertisement import PredictionResult, ActionStatus
    from errors import AdvertisementNotFoundError

    mock_ml = AsyncMock(spec=AdvertisementMLService)
    mock_ml.predict = AsyncMock(return_value=PredictionResult(is_violation=False, probability=0.1))
    mock_ml.close_advertisement = AsyncMock(return_value=ActionStatus(success=True))
    mock_ml.simple_predict = AsyncMock(return_value=PredictionResult(is_violation=False, probability=0.1))
    app.state.ml_service = mock_ml

    moderation_service = AsyncModerationService()
    moderation_service.producer = AsyncMock()
    moderation_service.producer.send_moderation_request = AsyncMock()
    app.state.moderation_service = moderation_service

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client