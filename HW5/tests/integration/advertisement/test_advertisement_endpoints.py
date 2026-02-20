import pytest
from fastapi import status
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from errors import AdvertisementNotFoundError, ModelNotReadyError


@pytest.mark.integration
class TestPredictEndpoint:
    @pytest.mark.parametrize("payload,expected_violation,expected_prob", [
        ({"seller_id": 1, "is_verified_seller": True, "item_id": 1, "name": "Safe", "description": "Good", "category": 1, "images_qty": 5}, False, 0.1),
        ({"seller_id": 2, "is_verified_seller": False, "item_id": 2, "name": "Bad", "description": "Spam", "category": 99, "images_qty": 0}, True, 0.9)])
    def test_predict_success(self, client, mock_ml_service, payload, expected_violation, expected_prob):
        mock_ml_service.predict.return_value = (expected_violation, expected_prob)
        response = client.post("/advertisement/predict", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_violation"] == expected_violation
        assert data["probability"] == expected_prob

    @pytest.mark.parametrize("missing_field", ["seller_id", "is_verified_seller", "item_id", "name", "description", "category", "images_qty"])
    def test_predict_missing_fields(self, client, missing_field):
        full_data = {"seller_id": 1, "is_verified_seller": True, "item_id": 1, "name": "Test", "description": "desc", "category": 1, "images_qty": 5}
        del full_data[missing_field]
        response = client.post("/advertisement/predict", json=full_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.parametrize("field,invalid_value", [
        ("seller_id", "abc"), ("item_id", "xyz"), ("category", "abc"), ("images_qty", "abc"), ("is_verified_seller", "yes_please"), ("name", 123), ("description", 456)])
    def test_predict_type_errors(self, client, field, invalid_value):
        payload = {"seller_id": 1, "is_verified_seller": True, "item_id": 1, "name": "Test", "description": "desc", "category": 1, "images_qty": 5}
        payload[field] = invalid_value
        response = client.post("/advertisement/predict", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.parametrize("field,invalid_data", [
        ("item_id", -7), ("category", 121), ("category", -1), ("images_qty", -5)])
    def test_predict_constraints(self, client, field, invalid_data):
        payload = {"seller_id": 1, "is_verified_seller": True, "item_id": 1, "name": "Test", "description": "desc", "category": 1, "images_qty": 5}
        payload[field] = invalid_data
        response = client.post("/advertisement/predict", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.parametrize("field,empty_value", [("name", ""), ("description", "")])
    def test_predict_empty_strings(self, client, field, empty_value):
        payload = {"seller_id": 1, "is_verified_seller": True, "item_id": 1, "name": "Test", "description": "desc", "category": 1, "images_qty": 5}
        payload[field] = empty_value
        response = client.post("/advertisement/predict", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.parametrize("exception,expected_status", [
        (ModelNotReadyError(""), status.HTTP_503_SERVICE_UNAVAILABLE),
        (Exception(""), status.HTTP_500_INTERNAL_SERVER_ERROR)])
    def test_predict_service_errors(self, client, mock_ml_service, exception, expected_status):
        mock_ml_service.predict.side_effect = exception
        payload = {"seller_id": 1, "is_verified_seller": True, "item_id": 1, "name": "Test", "description": "desc", "category": 1, "images_qty": 5}
        response = client.post("/advertisement/predict", json=payload)
        assert response.status_code == expected_status


@pytest.mark.integration
class TestSimplePredictEndpoint:

    @pytest.mark.parametrize("item_id,expected_violation,expected_prob", [
        (1, False, 0.1), (2, True, 0.9)])
    def test_simple_predict_success(self, client, mock_ml_service, item_id, expected_violation, expected_prob):
        mock_ml_service.simple_predict.return_value = (expected_violation, expected_prob)
        response = client.post("/advertisement/simple_predict", json={"item_id": item_id})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_violation"] == expected_violation
        assert data["probability"] == expected_prob

    def test_simple_predict_missing_fields(self, client):
        response = client.post("/advertisement/simple_predict", json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.parametrize("field,invalid_value", [("item_id", "abc")])
    def test_simple_predict_type_errors(self, client, field, invalid_value):
        payload = {"item_id": 1}
        payload[field] = invalid_value
        response = client.post("/advertisement/simple_predict", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.parametrize("invalid_data", [-1, 0])
    def test_simple_predict_constraints(self, client, invalid_data):
        response = client.post("/advertisement/simple_predict", json={"item_id": invalid_data})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.parametrize("exception,expected_status", [
        (AdvertisementNotFoundError(""), status.HTTP_404_NOT_FOUND),
        (ModelNotReadyError(""), status.HTTP_503_SERVICE_UNAVAILABLE),
        (Exception(""), status.HTTP_500_INTERNAL_SERVER_ERROR)])
    def test_simple_predict_service_errors(self, client, mock_ml_service, exception, expected_status):
        mock_ml_service.simple_predict.side_effect = exception
        response = client.post("/advertisement/simple_predict", json={"item_id": 1})
        assert response.status_code == expected_status


@pytest.mark.integration
class TestCloseAdvertisementEndpoint:
    def test_close_success(self, client, mock_ml_service):
        mock_ml_service.close_advertisement.return_value = True
        response = client.post("/advertisement/close", json={"item_id": 123})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Advertisement closed successfully"
        assert data["item_id"] == 123
        mock_ml_service.close_advertisement.assert_called_once()

    def test_close_not_found(self, client, mock_ml_service):
        mock_ml_service.close_advertisement.return_value = False
        response = client.post("/advertisement/close", json={"item_id": 999})
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data
        mock_ml_service.close_advertisement.assert_called_once()

    def test_close_validation_error(self, client):
        response = client.post("/advertisement/close", json={"item_id": -1})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        response = client.post("/advertisement/close", json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT