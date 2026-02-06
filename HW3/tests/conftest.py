import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from routers.advertisement import router as advertisement_router

@pytest.fixture
def mock_ml_service():
    mock = MagicMock()
    mock.is_model_ready.return_value = True
    mock.predict_ml.return_value = (False, 0.1)
    mock.simple_predict = AsyncMock()
    mock.simple_predict.return_value = (False, 0.1)
    return mock

@pytest.fixture
def app(mock_ml_service):
    app = FastAPI()
    app.include_router(advertisement_router, prefix="/advertisement")
    app.state.ml_service = mock_ml_service
    return app

@pytest.fixture
def test_client(app):
    with TestClient(app) as client:
        yield client

@pytest.fixture
def mock_ml_service_predict_only():
    mock = MagicMock()
    mock.is_model_ready.return_value = True
    mock.predict_ml.return_value = (False, 0.1)
    return mock

@pytest.fixture
def app_predict_only(mock_ml_service_predict_only):
    app = FastAPI()
    app.include_router(advertisement_router, prefix="/advertisement")
    app.state.ml_service = mock_ml_service_predict_only
    return app

@pytest.fixture
def test_client_predict_only(app_predict_only):
    with TestClient(app_predict_only) as client:
        yield client