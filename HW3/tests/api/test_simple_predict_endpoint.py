import pytest
import numpy as np
from http import HTTPStatus
from typing import Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from main import app
from models.advertisement import AdvModel

@pytest.mark.asyncio
async def test_simple_predict_success(app_client: TestClient):
    app_client.app.state.ml_service.simple_predict.return_value = (True, 0.85)
    
    response = app_client.post("/advertisement/simple_predict", json={"item_id": 123})
    
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert result["is_violation"] == True
    assert result["probability"] == 0.85

@pytest.mark.asyncio
async def test_simple_predict_not_found(app_client: TestClient):
    from errors import AdvertisementNotFoundError
    
    app_client.app.state.ml_service.simple_predict.side_effect = AdvertisementNotFoundError("Not found")
    
    response = app_client.post("/advertisement/simple_predict", json={"item_id": 999})
    
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "Advertisement with id 999 not found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_simple_predict_model_not_ready(app_client: TestClient):
    app_client.app.state.ml_service.is_model_ready.return_value = False
    
    response = app_client.post("/advertisement/simple_predict", json={"item_id": 123})
    
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert "Model is not available" in response.json()["detail"]

@pytest.mark.asyncio
async def test_simple_predict_validation_error(app_client: TestClient):
    # Неверный тип данных
    response = app_client.post("/advertisement/simple_predict", json={"item_id": "invalid"})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    
    # Отрицательное значение
    response = app_client.post("/advertisement/simple_predict", json={"item_id": -1})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    
    # Отсутствует обязательное поле
    response = app_client.post("/advertisement/simple_predict", json={})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY