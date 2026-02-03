import pytest
import numpy as np
from typing import Dict, Any
from unittest.mock import MagicMock
from http import HTTPStatus
from fastapi.testclient import TestClient
from main import app

@pytest.mark.parametrize("data, expected_violation",
    [({"seller_id":1, "is_verified_seller":False, "item_id":1, "name":"Test", "description":"a"*10, "category":0, "images_qty":0}, True),
     ({"seller_id":1, "is_verified_seller":True, "item_id":1, "name":"Test", "description":"OK", "category":50, "images_qty":5}, False)])
def test_predict_ml_success(app_client: TestClient, data: Dict[str, Any], expected_violation: bool):
    mock_proba = np.array([[0.4, 0.6]]) if expected_violation else np.array([[0.7, 0.3]])
    app_client.app.state.ml_service._model.predict_proba.return_value = mock_proba
    
    resp = app_client.post("/advertisement/predict", json=data)
    assert resp.status_code == HTTPStatus.OK
    result = resp.json()
    assert result["is_violation"] == expected_violation
    assert 0 <= result["probability"] <= 1

def test_invalid_data(app_client: TestClient) -> None:
    data = {"seller_id": -1, "is_verified_seller": True, "item_id": 1, "name": "", "description": "test", "category": 1, "images_qty": 0}
    resp = app_client.post("/advertisement/predict", json=data)
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

def test_model_unavailable(app_client: TestClient) -> None:
    app_client.app.state.ml_service._model = None
    
    data={"seller_id":1,"is_verified_seller":False,"item_id":1,"name":"Test","description":"test","category":0,"images_qty":0}
    resp = app_client.post("/advertisement/predict", json=data)
    assert resp.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert "Model is not available" in resp.json()["detail"]