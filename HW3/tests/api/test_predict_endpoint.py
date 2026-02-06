import pytest
import numpy as np
from http import HTTPStatus
from typing import Dict, Any
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app 

@pytest.mark.parametrize('input_data, expected_violation', 
    [({"seller_id": 1, "is_verified_seller": True, "id": 1, "name": "Safe Item", "description": "Good desc", "category": 1, "images_qty": 5}, False),
     ({"seller_id": 1, "is_verified_seller": False, "id": 1, "name": "Bad Item", "description": "Spam", "category": 1, "images_qty": 0}, True)])
def test_predict_logic(app_client: TestClient, input_data: Dict[str, Any], expected_violation: bool) -> None:
    if expected_violation:
        app_client.app.state.ml_service.predict_ml.return_value = (True, 0.9)
    else:
        app_client.app.state.ml_service.predict_ml.return_value = (False, 0.1)

    response = app_client.post("/advertisement/predict", json=input_data)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    
    assert result["is_violation"] == expected_violation
    assert "probability" in result
    assert 0 <= result["probability"] <= 1

    if expected_violation:
        assert result["probability"] > 0.5
    else:
        assert result["probability"] <= 0.5

@pytest.mark.parametrize('invalid_data',
    [{"seller_id": 1, "is_verified_seller": True, "id": 1, "name": "Test", "category": 1, "images_qty": 0},
     {"seller_id": "invalid", "is_verified_seller": True, "id": 1, "name": "Test", "description": "desc", "category": 1, "images_qty": 0},
     {"seller_id": -1, "is_verified_seller": False, "id": 1, "name": "Test", "description": "desc", "category": 1, "images_qty": 5}])
def test_predict_validation_general(app_client: TestClient, invalid_data: dict) -> None:
    response = app_client.post("/advertisement/predict", json=invalid_data)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

def test_predict_empty_body(app_client: TestClient) -> None:
    response = app_client.post("/advertisement/predict", json={})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

@pytest.mark.parametrize("missing_field", ["seller_id", "is_verified_seller", "id", "name", "description", "category", "images_qty"])
def test_predict_missing_fields(app_client: TestClient, missing_field: str) -> None:
    full_data = {"seller_id": 1, "is_verified_seller": True, "id": 1,
        "name": "Test", "description": "Test desc", "category": 1, "images_qty": 5}
    del full_data[missing_field]
    
    response = app_client.post("/advertisement/predict", json=full_data)
    
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    error_detail = response.json()["detail"]
    field_errors = [err for err in error_detail if err["loc"][1] == missing_field]
    assert len(field_errors) > 0, f"Expected error for field '{missing_field}', got errors: {error_detail}"

@pytest.mark.parametrize("field, type_error_data", 
   [("seller_id", "abc"), 
    ("id", "xyz"),
    ("category", "invalid"), 
    ("images_qty", "five"), 
    ("is_verified_seller", "yes_please")])
def test_predict_type_validation(app_client: TestClient, field: str, type_error_data: Any) -> None:
    full_data = {"seller_id": 1, "is_verified_seller": True, "id": 1,
        "name": "Test", "description": "Test desc", "category": 1, "images_qty": 5}
    full_data[field] = type_error_data
    
    response = app_client.post("/advertisement/predict", json=full_data)
    
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    error_detail = response.json()["detail"]
    
    field_type_errors = [err for err in error_detail if err["loc"][1] == field]
    assert len(field_type_errors) > 0

@pytest.mark.parametrize("empty_field", ["name", "description"])
def test_predict_empty_strings(app_client: TestClient, empty_field: str) -> None: 
    full_data = {"seller_id": 1, "is_verified_seller": True, "id": 1,
        "name": "Test", "description": "Test desc", "category": 1, "images_qty": 5}
    full_data[empty_field] = ""
    
    response = app_client.post("/advertisement/predict", json=full_data)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

def test_model_unavailable_503(app_client: TestClient) -> None:
    valid_data = {
        "seller_id": 1, "is_verified_seller": True, "id": 1,
        "name": "Test", "description": "Test", "category": 1, "images_qty": 5}

    app_client.app.state.ml_service.is_model_ready.return_value = False
    
    response = app_client.post("/advertisement/predict", json=valid_data)
    
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert "Model is not available" in response.json()["detail"]

def test_prediction_internal_error_500(app_client: TestClient) -> None:
    valid_data = {"seller_id": 1, "is_verified_seller": True, "id": 1, "name": "Test", "description": "Test", "category": 1, "images_qty": 5}
    
    app_client.app.state.ml_service.predict_ml.side_effect = ValueError("Corrupted tensor shape")
    
    response = app_client.post("/advertisement/predict", json=valid_data)
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.parametrize("data, expected_violation",
    [({"seller_id":1, "is_verified_seller":False, "id":1, "name":"Test", "description":"a"*10, "category":0, "images_qty":0}, True),
     ({"seller_id":1, "is_verified_seller":True, "id":1, "name":"Test", "description":"OK", "category":50, "images_qty":5}, False)])
def test_predict_ml_success(app_client: TestClient, data: Dict[str, Any], expected_violation: bool):
    if expected_violation:
        app_client.app.state.ml_service.predict_ml.return_value = (True, 0.6)
    else:
        app_client.app.state.ml_service.predict_ml.return_value = (False, 0.3)
    
    resp = app_client.post("/advertisement/predict", json=data)
    assert resp.status_code == HTTPStatus.OK
    result = resp.json()
    assert result["is_violation"] == expected_violation
    assert 0 <= result["probability"] <= 1

@pytest.mark.parametrize("valid_data",
        [{"seller_id": 1, "is_verified_seller": False, "id": 1, "name": "Test", "description": "test", "category": 0, "images_qty": 0},
        {"seller_id": 2, "is_verified_seller": True, "id": 2, "name": "Test Item", "description": "Test description", "category": 5, "images_qty": 3},
        {"seller_id": 3, "is_verified_seller": True, "id": 3, "name": "Max Item", "description": "x" * 1000, "category": 100, "images_qty": 10},
        {"seller_id": 4, "is_verified_seller": False, "id": 4, "name": "Min", "description": "x", "category": 0, "images_qty": 0},
        {"seller_id": 5, "is_verified_seller": True, "id": 5, "name": "Mid Category", "description": "Middle category item", "category": 50, "images_qty": 5}])
def test_model_unavailable(app_client: TestClient, valid_data: Dict[str, Any]) -> None:
    app_client.app.state.ml_service.is_model_ready.return_value = False
    
    resp = app_client.post("/advertisement/predict", json=valid_data)

    assert resp.status_code == HTTPStatus.SERVICE_UNAVAILABLE

    response_json = resp.json()
    assert "Model is not available" in response_json["detail"]


@pytest.mark.parametrize("invalid_data",
    # Отрицательное значение идентификатора
    [{"seller_id": -1, "is_verified_seller": True, "id": 1, "name": "", "description": "test", "category": 1, "images_qty": 0},
    # Пустое значение названия
    {"seller_id": 1, "is_verified_seller": True, "id": 1, "name": "", "description": "test", "category": 1, "images_qty": 5},
    # Пустое значение описания
    {"seller_id": 1, "is_verified_seller": True, "id": 1, "name": "Test", "description": "", "category": 1, "images_qty": 5},
    # Значение категории меньше 0
    {"seller_id": 1, "is_verified_seller": True, "id": 1, "name": "Test", "description": "test", "category": -1, "images_qty": 5},
    # Значение категории больше 100
    {"seller_id": 1, "is_verified_seller": True, "id": 1, "name": "Test", "description": "test", "category": 101, "images_qty": 5},
    # Значение количества изображений меньше 0
    {"seller_id": 1, "is_verified_seller": True, "id": 1, "name": "Test", "description": "test", "category": 1, "images_qty": -1},
    # Значение количества изображений больше 10
    {"seller_id": 1, "is_verified_seller": True, "id": 1, "name": "Test", "description": "test", "category": 1, "images_qty": 11}])
def test_invalid_data(app_client: TestClient, invalid_data: Dict[str, Any]) -> None:
    resp = app_client.post("/advertisement/predict", json=invalid_data)
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY