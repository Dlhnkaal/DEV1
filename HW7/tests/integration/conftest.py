import asyncio
from typing import AsyncGenerator, Generator
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from main import app as real_app
from dependencies import get_current_account
from models.account import AccountModel


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
async def async_client(app: FastAPI) -> AsyncGenerator:
    # Use ASGITransport to communicate with the app
    transport = ASGITransport(app=app)
    
    # Import correct services based on dependencies.py
    from services.advertisement import AdvertisementMLService
    from services.moderation import AsyncModerationService
    from models.advertisement import PredictionResult, ActionStatus
    
    # Mock ML Service
    app.state.ml_service = AsyncMock(spec=AdvertisementMLService)
    app.state.ml_service.simple_predict.return_value = PredictionResult(is_violation=False, probability=0.1)
    app.state.ml_service.predict.return_value = PredictionResult(is_violation=False, probability=0.1)
    app.state.ml_service.close_advertisement.return_value = ActionStatus(success=True)

    # Mock Moderation Service (instantiate normally, without `producer=`)
    app.state.moderation_service = AsyncModerationService()
    app.state.moderation_service.start_moderation = AsyncMock()
    
    class MockResult:
        task_id = 1
        status = "pending"
        message = "Started"
        id = 1
        is_violation = False
        probability = 0.0

    app.state.moderation_service.start_moderation.return_value = MockResult()
    app.state.moderation_service.get_moderation_status = AsyncMock(return_value=MockResult())
    
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
