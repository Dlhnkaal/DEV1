import asyncio
from typing import AsyncGenerator, Generator
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch

from main import app as real_app
from dependencies import get_current_account
from models.account import AccountModel

@pytest.fixture
def mock_account() -> AccountModel:
    return AccountModel(id=1, login="test_user", password="hashed", is_blocked=False)

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
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client