import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from main import app
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