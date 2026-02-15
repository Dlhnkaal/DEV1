import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status
from httpx import AsyncClient, ASGITransport
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from main import app
from models.moderation import (
    AsyncPredictionResponse, 
    ModerationResultInDB
)
from workers.moderation_worker import ModerationWorker
from errors import AdvertisementNotFoundError, ModerationTaskNotFoundError


@pytest_asyncio.fixture
async def async_client():
    mock_service = MagicMock()
    mock_service.start_moderation = AsyncMock()      
    mock_service.get_moderation_status = AsyncMock()
    
    old_service = getattr(app.state, "moderation_service", None)
    app.state.moderation_service = mock_service
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, mock_service
        
    if old_service:
        app.state.moderation_service = old_service
    elif hasattr(app.state, "moderation_service"):
        del app.state.moderation_service


@pytest.fixture
def mock_repo():
    with patch("services.moderation.ModerationRepository") as MockRepo:
        repo = MockRepo.return_value
        repo.check_advertisement_exists = AsyncMock(return_value=True)
        repo.create_pending = AsyncMock()
        repo.get_result_by_id = AsyncMock()
        repo.update_result = AsyncMock()
        yield repo