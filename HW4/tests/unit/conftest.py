import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from main import app
from services.advertisement import AdvertisementMLService
from repositories.advertisement import AdvertisementPostgresStorage, AdvertisementRepository
from repositories.user import UserPostgresStorage


@pytest.fixture
def mock_ad_storage():
    storage = AsyncMock(spec=AdvertisementPostgresStorage)
    storage.create.return_value = {
        "id": 1, "seller_id": 1, "name": "test", "description": "desc",
        "category": 1, "images_qty": 1, "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00"}
    storage.get_by_id_with_user.return_value = {
        "item_id": 1, "seller_id": 1, "name": "test", "description": "desc",
        "category": 1, "images_qty": 1, "is_verified_seller": True}
    storage.get_all.return_value = []
    storage.delete.return_value = {"id": 1}
    return storage

@pytest.fixture
def mock_user_storage():
    now = datetime.now() 
    storage = AsyncMock(spec=UserPostgresStorage)
    storage.create.return_value = {
        "id": 1, "login": "user", "password": "hashed777", "email": "u@ex.com",
        "is_verified_seller": False, "created_at": now,
        "updated_at": now}
    storage.get_by_id.return_value = {
        "id": 1, "login": "user", "password": "hashed777", "email": "u@ex.com",
        "is_verified_seller": False, "created_at": now,
        "updated_at": now}
    storage.get_all.return_value = []
    return storage

@pytest.fixture
def mock_ad_repo(mock_ad_storage):
    repo = AdvertisementRepository()
    repo.storage = mock_ad_storage
    return repo


@pytest.fixture
def mock_ml_service(mock_ad_repo):
    service = MagicMock(spec=AdvertisementMLService)
    service.predict.return_value = (False, 0.1)
    service.simple_predict.return_value = (False, 0.1)
    service.advertisement_repo = mock_ad_repo
    return service


@pytest.fixture(autouse=True)
def _patch_model_loading():
    with patch.object(AdvertisementMLService, "_load_model", return_value=None):
        yield


@pytest.fixture
def client(mock_ml_service):
    from routers.advertisement import get_ml_service
    app.dependency_overrides[get_ml_service] = lambda: mock_ml_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()