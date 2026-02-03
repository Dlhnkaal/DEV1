import pytest
import numpy as np
from http import HTTPStatus
from typing import Dict, Any
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app 

@pytest.mark.parametrize('input_data, expected_violation', 
    [({"seller_id": 1, "is_verified_seller": True, "item_id": 1, "name": "Safe Item", "description": "Good desc", "category": 1, "images_qty": 5}, False),
     ({"seller_id": 1, "is_verified_seller": False, "item_id": 1, "name": "Bad Item", "description": "Spam", "category": 1, "images_qty": 0}, True)])
def test_predict_logic(app_client: TestClient, input_data: Dict[str, Any], expected_violation: bool) -> None:
    mock_proba = np.array([[0.1, 0.9]]) if expected_violation else np.array([[0.9, 0.1]])
    app_client.app.state.ml_service._model.predict_proba.return_value = mock_proba

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
    [{"seller_id": 1, "is_verified_seller": True, "item_id": 1, "name": "Test", "category": 1, "images_qty": 0},
     {"seller_id": "invalid", "is_verified_seller": True, "item_id": 1, "name": "Test", "description": "desc", "category": 1, "images_qty": 0},
     {"seller_id": -1, "is_verified_seller": False, "item_id": 1, "name": "Test", "description": "desc", "category": 1, "images_qty": 5}])
def test_predict_validation_general(app_client: TestClient, invalid_data: dict) -> None:
    response = app_client.post("/advertisement/predict", json=invalid_data)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

def test_predict_empty_body(app_client: TestClient) -> None:
    response = app_client.post("/advertisement/predict", json={})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

@pytest.mark.parametrize("missing_field", ["seller_id", "is_verified_seller", "item_id", "name", "description", "category", "images_qty"])
def test_predict_missing_fields(app_client: TestClient, missing_field: str) -> None:
    full_data = {"seller_id": 1, "is_verified_seller": True, "item_id": 1,
        "name": "Test", "description": "Test desc", "category": 1, "images_qty": 5}
    del full_data[missing_field]
    
    response = app_client.post("/advertisement/predict", json=full_data)
    
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    error_detail = response.json()["detail"]
    field_errors = [err for err in error_detail if err["loc"][1] == missing_field]
    assert len(field_errors) > 0

@pytest.mark.parametrize("field, type_error_data", 
   [("seller_id", "abc"), 
    ("item_id", "xyz"), 
    ("category", "invalid"), 
    ("images_qty", "five"), 
    ("is_verified_seller", "yes_please")])
def test_predict_type_validation(app_client: TestClient, field: str, type_error_data: Any) -> None:
    full_data = {
        "seller_id": 1, "is_verified_seller": True, "item_id": 1,
        "name": "Test", "description": "Test desc", "category": 1, "images_qty": 5}
    full_data[field] = type_error_data
    
    response = app_client.post("/advertisement/predict", json=full_data)
    
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    error_detail = response.json()["detail"]
    
    field_type_errors = [err for err in error_detail if err["loc"][1] == field]
    assert len(field_type_errors) > 0

@pytest.mark.parametrize("empty_field", ["name", "description"])
def test_predict_empty_strings(app_client: TestClient, empty_field: str) -> None: 
    full_data = {
        "seller_id": 1, "is_verified_seller": True, "item_id": 1,
        "name": "Test", "description": "Test desc", "category": 1, "images_qty": 5}
    full_data[empty_field] = ""
    
    response = app_client.post("/advertisement/predict", json=full_data)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

def test_model_unavailable_503(app_client: TestClient) -> None:
    valid_data = {
        "seller_id": 1, "is_verified_seller": True, "item_id": 1,
        "name": "Test", "description": "Test", "category": 1, "images_qty": 5}
    app_client.app.state.ml_service._model = None
    
    response = app_client.post("/advertisement/predict", json=valid_data)
    
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert "Model is not available" in response.json()["detail"]

def test_prediction_internal_error_500(app_client: TestClient) -> None:
    valid_data = {"seller_id": 1, "is_verified_seller": True, "item_id": 1, "name": "Test", "description": "Test", "category": 1, "images_qty": 5}
    
    app_client.app.state.ml_service._model.predict_proba.side_effect = ValueError("Corrupted tensor shape")
    
    response = app_client.post("/advertisement/predict", json=valid_data)
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR