import pytest
import sys 
import os
import fastapi
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from main import app
from HW2.services.advertisement import AdvertisementMLService


@pytest.fixture
def app_client() -> TestClient:
    mock_model = MagicMock()
    mock_service = AdvertisementMLService()
    mock_service._model = mock_model
    
    app.state.ml_service = mock_service
    
    return TestClient(app)