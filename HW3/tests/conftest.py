import pytest
import sys
import os
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from main import app
from services.advertisement import AdvertisementMLService

@pytest.fixture
def app_client():
    mock_model = MagicMock()
    mock_service = MagicMock(spec=AdvertisementMLService)
    mock_service._model = mock_model
    mock_service.is_model_ready.return_value = True
    mock_service.predict_ml.return_value = (True, 0.8)
    mock_service.simple_predict = AsyncMock(return_value=(True, 0.8))

    app.state.ml_service = mock_service
    return TestClient(app)

@pytest.fixture
def sample_advertisement_data():
    return {"seller_id": 1,
        "is_verified_seller": True,
        "id": 1,
        "name": "Test Item",
        "description": "This is a test description for the item.",
        "category": 5,
        "images_qty": 3    }