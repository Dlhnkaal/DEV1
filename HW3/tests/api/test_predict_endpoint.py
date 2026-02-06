import pytest
from http import HTTPStatus
from typing import Dict, Any

@pytest.mark.parametrize("input_data, expected_violation", [
    ({"seller_id":1, "is_verified_seller":True, "id":1, "name":"Safe", "description":"Good", "category":1, "images_qty":5}, False),
    ({"seller_id":1, "is_verified_seller":False, "id":1, "name":"Bad", "description":"Spam", "category":1, "images_qty":0}, True)])
def test_predict_logic(test_client_predict_only, mock_ml_service_predict_only, input_data, expected_violation):
    if expected_violation:
        mock_ml_service_predict_only.predict_ml.return_value = (True, 0.9)
    else:
        mock_ml_service_predict_only.predict_ml.return_value = (False, 0.1)

    response = test_client_predict_only.post("/advertisement/predict", json=input_data)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert result["is_violation"] == expected_violation
    assert 0 <= result["probability"] <= 1

@pytest.mark.parametrize("invalid_data", [
    {"seller_id":1, "is_verified_seller":True, "id":1, "name":"Test", "category":1, "images_qty":0},
    {"seller_id":"invalid", "is_verified_seller":True, "id":1, "name":"Test", "description":"desc", "category":1, "images_qty":0},
    {"seller_id":-1, "is_verified_seller":False, "id":1, "name":"Test", "description":"desc", "category":1, "images_qty":5}])
def test_predict_validation_general(test_client_predict_only, mock_ml_service_predict_only, invalid_data):
    response = test_client_predict_only.post("/advertisement/predict", json=invalid_data)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

@pytest.mark.parametrize("missing_field", ["seller_id", "is_verified_seller", "id", "name", "description", "category", "images_qty"])
def test_predict_missing_fields(test_client_predict_only, mock_ml_service_predict_only, missing_field):
    full_data = {"seller_id":1, "is_verified_seller":True, "id":1, "name":"Test", "description":"Test desc", "category":1, "images_qty":5}
    del full_data[missing_field]
    response = test_client_predict_only.post("/advertisement/predict", json=full_data)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

@pytest.mark.parametrize("field, type_error_data", [
    ("seller_id", "abc"), ("id", "xyz"), ("category", "invalid"), ("images_qty", "five"), ("is_verified_seller", "yes_please")])
def test_predict_type_validation(test_client_predict_only, mock_ml_service_predict_only, field, type_error_data):
    full_data = {"seller_id":1, "is_verified_seller":True, "id":1, "name":"Test", "description":"Test desc", "category":1, "images_qty":5}
    full_data[field] = type_error_data
    response = test_client_predict_only.post("/advertisement/predict", json=full_data)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

@pytest.mark.parametrize("empty_field", ["name", "description"])
def test_predict_empty_strings(test_client_predict_only, mock_ml_service_predict_only, empty_field):
    full_data = {"seller_id":1, "is_verified_seller":True, "id":1, "name":"Test", "description":"Test desc", "category":1, "images_qty":5}
    full_data[empty_field] = ""
    response = test_client_predict_only.post("/advertisement/predict", json=full_data)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

def test_model_unavailable_503(test_client_predict_only, mock_ml_service_predict_only):
    mock_ml_service_predict_only.is_model_ready.return_value = False
    response = test_client_predict_only.post("/advertisement/predict", json={"seller_id":1, "is_verified_seller":True, "id":1, "name":"Test", "description":"Test", "category":1, "images_qty":5})
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE

def test_prediction_internal_error_500(test_client_predict_only, mock_ml_service_predict_only):
    mock_ml_service_predict_only.predict_ml.side_effect = ValueError("Corrupted tensor shape")
    response = test_client_predict_only.post("/advertisement/predict", json={"seller_id":1, "is_verified_seller":True, "id":1, "name":"Test", "description":"Test", "category":1, "images_qty":5})
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

@pytest.mark.parametrize("invalid_data", [
    {"seller_id":-1, "is_verified_seller":True, "id":1, "name":"", "description":"test", "category":1, "images_qty":0},
    {"seller_id":1, "is_verified_seller":True, "id":1, "name":"", "description":"test", "category":1, "images_qty":5},
    {"seller_id":1, "is_verified_seller":True, "id":1, "name":"Test", "description":"", "category":1, "images_qty":5},
    {"seller_id":1, "is_verified_seller":True, "id":1, "name":"Test", "description":"test", "category":-1, "images_qty":5},
    {"seller_id":1, "is_verified_seller":True, "id":1, "name":"Test", "description":"test", "category":101, "images_qty":5},
    {"seller_id":1, "is_verified_seller":True, "id":1, "name":"Test", "description":"test", "category":1, "images_qty":-1},
    {"seller_id":1, "is_verified_seller":True, "id":1, "name":"Test", "description":"test", "category":1, "images_qty":11}])
def test_invalid_data(test_client_predict_only, mock_ml_service_predict_only, invalid_data):
    response = test_client_predict_only.post("/advertisement/predict", json=invalid_data)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY