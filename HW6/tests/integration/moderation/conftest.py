import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from httpx import AsyncClient, ASGITransport
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from main import app
from services.moderation import AsyncModerationService
from models.moderation import ModerationTaskResult, ModerationResultInDB


@pytest_asyncio.fixture
async def async_client():
    mock_service = AsyncMock(spec=AsyncModerationService)

    mock_service.start_moderation.return_value = ModerationTaskResult(
        task_id=123,
        status="pending",
        message="Moderation request accepted"
    )

    mock_service.get_moderation_status.return_value = ModerationResultInDB(
        id=123,
        item_id=55,
        status="completed",
        is_violation=True,
        probability=0.95,
        error_message=None,
        created_at="2024-01-01T00:00:00",
        processed_at="2024-01-01T00:00:01"
    )

    old_service = getattr(app.state, "moderation_service", None)
    app.state.moderation_service = mock_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, mock_service

    if old_service:
        app.state.moderation_service = old_service
    elif hasattr(app.state, "moderation_service"):
        del app.state.moderation_service