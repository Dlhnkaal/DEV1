import pytest
from fastapi.testclient import TestClient
from main import app
from http import HTTPStatus
from models.advertisement import AdvModel
from pydantic import ValidationError

@pytest.mark.parametrize('input_data, expected_result', 
    [({"seller_id": 1, "is_verified_seller": True, "item_id": 1, "name": "Test", "description": "Test desc", "category": 1, "images_qty": 0}, True),
    ({"seller_id": 1, "is_verified_seller": False, "item_id": 1, "name": "Test", "description": "Test desc", "category": 1, "images_qty": 5}, True),    
    ({"seller_id": 1, "is_verified_seller": False, "item_id": 1, "name": "Test", "description": "Test desc", "category": 1, "images_qty": 0}, False)])
def test_predict_logic(app_client: TestClient, input_data: dict, expected_result: bool):
    response = app_client.post("/advertisement/predict", json=input_data)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert result["resp"] == expected_result

@pytest.mark.parametrize('invalid_data',
    # Отсутствует обязательное поле
    [{"seller_id": 1, "is_verified_seller": True, "item_id": 1, "name": "Test", "category": 1, "images_qty": 0},
    # Неправильный тип
    {"seller_id": "invalid", "is_verified_seller": True, "item_id": 1, "name": "Test", "description": "desc", "category": 1, "images_qty": 0},
    # Отрицательное значение
    {"seller_id": -1, "is_verified_seller": False, "item_id": 1, "name": "Test", "description": "desc", "category": 1, "images_qty": -1}])
def test_predict_validation(app_client: TestClient, invalid_data: dict):
    response = app_client.post("/advertisement/predict", json=invalid_data)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

def test_predict_internal_error(app_client: TestClient):
    response = app_client.post("/advertisement/predict", json={})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

@pytest.mark.parametrize("missing_field", ["seller_id", "is_verified_seller", "item_id", "name", "description", "category", "images_qty"])
def test_predict_missing_field(app_client: TestClient, missing_field: str):
    full_data = {
        "seller_id": 1, "is_verified_seller": True, "item_id": 1,
        "name": "Test", "description": "Test desc", "category": 1, "images_qty": 5}
    del full_data[missing_field]
    
    response = app_client.post("/advertisement/predict", json=full_data)
    
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    error_detail = response.json()["detail"]
    
    field_errors = [err["loc"][1] for err in error_detail if err["loc"][1] == missing_field]
    print(error_detail)
    assert len(field_errors) > 0

@pytest.mark.parametrize("field, type_error_data", 
    [("seller_id", "abc"),         
    ("item_id", "xyz"),       
    ("category", "invalid"),     
    ("images_qty", -1),      
    ("is_verified_seller", "ye")])
def test_predict_type_validation(app_client: TestClient, field: str, type_error_data: any):
    full_data = {"seller_id": 1, "is_verified_seller": True, "item_id": 1,
        "name": "Test", "description": "Test desc", "category": 1, "images_qty": 5}
    full_data[field] = type_error_data
    
    response = app_client.post("/advertisement/predict", json=full_data)
    
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    error_detail = response.json()["detail"]

    field_type_errors = [err for err in error_detail if err["loc"][1] == field]
    assert len(field_type_errors) > 0

@pytest.mark.parametrize("empty_field", ["name", "description"])
def test_predict_empty_string(app_client: TestClient, empty_field: str):
    full_data = {"seller_id": 1, "is_verified_seller": True, "item_id": 1,
        "name": "Test", "description": "Test desc", "category": 1, "images_qty": 5}
    
    full_data[empty_field] = ""
    
    response = app_client.post("/advertisement/predict", json=full_data)
    
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
