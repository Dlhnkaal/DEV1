import pytest
from http import HTTPStatus
from typing import Dict, Any, Tuple

@pytest.mark.parametrize("model_return, expected_result", [
    ((True, 0.85), {"is_violation": True, "probability": 0.85}),
    ((False, 0.15), {"is_violation": False, "probability": 0.15})])
def test_simple_predict_success(test_client, mock_ml_service, model_return, expected_result):
    mock_ml_service.simple_predict.return_value = model_return
    
    response = test_client.post("/advertisement/simple_predict", json={"item_id": 123})
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert result == expected_result

def test_simple_predict_not_found(test_client, mock_ml_service):
    mock_ml_service.simple_predict.side_effect = Exception("Advertisement with id 999 not found")
    
    response = test_client.post("/advertisement/simple_predict", json={"item_id": 999})
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

def test_simple_predict_model_not_ready(test_client, mock_ml_service):
    mock_ml_service.is_model_ready.return_value = False
    
    response = test_client.post("/advertisement/simple_predict", json={"item_id": 123})
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE

@pytest.mark.parametrize("payload", [{"item_id": "invalid"}, {"item_id": -1},
    {"item_id": 0}, {}, {"item_id": None}])
def test_simple_predict_validation_error(test_client, mock_ml_service, payload):
    response = test_client.post("/advertisement/simple_predict", json=payload)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

def test_simple_predict_internal_error(test_client, mock_ml_service):
    mock_ml_service.simple_predict.side_effect = Exception("Database connection failed")
    
    response = test_client.post("/advertisement/simple_predict", json={"item_id": 123})
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR