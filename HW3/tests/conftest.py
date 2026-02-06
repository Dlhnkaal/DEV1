import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from main import app

@pytest.fixture
def mock_ml_service():
    mock = MagicMock()
    mock.is_model_ready.return_value = True
    mock.predict_ml.return_value = (False, 0.1)
    mock.simple_predict = AsyncMock()
    mock.simple_predict.return_value = (False, 0.1)
    return mock

@pytest.fixture
def app_client(mock_ml_service):
    app.state.ml_service = mock_ml_service
    with TestClient(app) as client:
        yield client

