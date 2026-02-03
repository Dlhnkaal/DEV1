import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app
from models.advertisement import AdvModel, PredictionMLResponse

@pytest.mark.parametrize("data, expected_violation", [
    ({"seller_id":1, "is_verified_seller":False, "item_id":1, "name":"Test", "description":"a"*10, "category":0, "images_qty":0}, True),
    ({"seller_id":1, "is_verified_seller":True, "item_id":1, "name":"Test", "description":"OK", "category":50, "images_qty":5}, False),
])
def test_predict_ml_success(client, data, expected_violation):
    with patch('services.advertisement.AdvertisementMLService._load_model') as mock_model:
        mock_model().predict_proba.return_value = np.array([[0.4, 0.6]]) if expected_violation else np.array([[0.7, 0.3]])
        resp = client.post("/advertisement/predict", json=data)
        assert resp.status_code == 200
        result = resp.json()
        assert result["is_violation"] == expected_violation
        assert 0 <= result["probability"] <= 1

def test_invalid_data(client):
    data = {"seller_id": -1, "is_verified_seller": True, "item_id": 1, "name": "", "description": "test", "category": 1, "images_qty": 0}
    resp = client.post("/advertisement/predict", json=data)
    assert resp.status_code == 422

def test_model_unavailable(client):
    with patch('services.advertisement.AdvertisementMLService._load_model', side_effect=Exception("No model")):
        data={"seller_id":1,"is_verified_seller":False,"item_id":1,"name":"Test","description":"test","category":0,"images_qty":0}
        resp = client.post("/advertisement/predict", json=data)
        assert resp.status_code == 500
