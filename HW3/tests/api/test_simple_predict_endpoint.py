import pytest
from http import HTTPStatus
from typing import Dict, Any, Tuple
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from routers.advertisement import router
from errors import AdvertisementNotFoundError

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
    app.include_router(router, prefix="/advertisement", tags=["prediction"])
    app.state.ml_service = mock_ml_service
    return app

@pytest.fixture
def test_client(app):
    with TestClient(app) as client:
        yield client

@pytest.mark.parametrize("model_return, expected_result", 
    [((True, 0.85), {"is_violation": True, "probability": 0.85}),
    ((False, 0.15), {"is_violation": False, "probability": 0.15})])
def test_simple_predict_success(test_client, app, mock_ml_service, model_return, expected_result):
    mock_ml_service.simple_predict.return_value = model_return
    
    response = test_client.post("/advertisement/simple_predict", json={"item_id": 123})
    
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert result == expected_result

def test_simple_predict_not_found(test_client, app, mock_ml_service):
    mock_ml_service.simple_predict.side_effect = AdvertisementNotFoundError("Advertisement with id 999 not found")
    
    response = test_client.post("/advertisement/simple_predict", json={"item_id": 999})
    assert response.status_code == HTTPStatus.NOT_FOUND

def test_simple_predict_model_not_ready(test_client, app, mock_ml_service):
    mock_ml_service.is_model_ready.return_value = False
    
    response = test_client.post("/advertisement/simple_predict", json={"item_id": 123})
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE

@pytest.mark.parametrize("payload", [{"item_id": "invalid"}, {"item_id": -1}, {"item_id": 0},
                                     {}, {"item_id": None}])
def test_simple_predict_validation_error(test_client, app, mock_ml_service, payload):
    response = test_client.post("/advertisement/simple_predict", json=payload)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

def test_simple_predict_internal_error(test_client, app, mock_ml_service):
    mock_ml_service.simple_predict.side_effect = Exception("Database connection failed")
    
    response = test_client.post("/advertisement/simple_predict", json={"item_id": 123})
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR