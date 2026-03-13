import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status

from errors import (
    AdvertisementNotFoundError,
    AuthorizedError,
    UnauthorizedError,
    ModerationTaskNotFoundError,
    ModelNotReadyError,
)

@pytest.mark.usefixtures("mock_current_account")
class TestAdvertisementRouter:
    @pytest.mark.parametrize("payload,status_code,response_body", [
        ({"seller_id": 1, "name": "Test", "description": "desc", "category": 1, "images_qty": 5, "item_id": 10, "is_verified_seller": True}, 200, {"is_violation": True, "probability": 0.8}),
        ({"seller_id": 1, "name": "Test", "description": "desc", "category": 1, "images_qty": 5, "item_id": 10, "is_verified_seller": True}, 503, None),  # модель недоступна
    ])
    async def test_predict(self, async_client: AsyncClient, payload, status_code, response_body):
        with patch("routers.advertisement.service.predict") as mock_predict:
            if status_code == 200:
                mock_predict.return_value = (response_body["is_violation"], response_body["probability"])
            else:
                mock_predict.side_effect = ModelNotReadyError()

            response = await async_client.post("/advertisement/predict", json=payload)
            assert response.status_code == status_code
            if status_code == 200:
                assert response.json() == response_body

    @pytest.mark.parametrize("payload,status_code,exception", [
        ({"item_id": 1}, 200, None),
        ({"item_id": 999}, 404, AdvertisementNotFoundError),
    ])
    async def test_simple_predict(self, async_client: AsyncClient, payload, status_code, exception):
        with patch("routers.advertisement.service.simple_predict") as mock_simple:
            if exception:
                mock_simple.side_effect = exception("Not found")
            else:
                mock_simple.return_value = (True, 0.9)

            response = await async_client.post("/advertisement/simple_predict", json=payload)
            assert response.status_code == status_code

    @pytest.mark.parametrize("payload,close_success,status_code", [
        ({"item_id": 1}, True, 200),
        ({"item_id": 2}, False, 404),
    ])
    async def test_close_advertisement(self, async_client: AsyncClient, payload, close_success, status_code):
        with patch("routers.advertisement.service.close_advertisement") as mock_close:
            mock_close.return_value = close_success
            response = await async_client.post("/advertisement/close", json=payload)
            assert response.status_code == status_code

class TestAuthRouter:
    @pytest.mark.parametrize("login,password,service_side_effect,expected_status", [
        ("user", "pass", None, 200),
        ("user", "wrong", AuthorizedError(), 400),
    ])
    async def test_login(self, async_client: AsyncClient, login, password, service_side_effect, expected_status):
        with patch("routers.auth.auth_service.login") as mock_login:
            if service_side_effect:
                mock_login.side_effect = service_side_effect
            else:
                mock_login.return_value = ("access", "refresh")

            response = await async_client.post("/auth/login", json={"login": login, "password": password})
            assert response.status_code == expected_status

    @pytest.mark.parametrize("cookies,service_side_effect,expected_status", [
        ({"x-refresh-token": "old"}, None, 200),
        ({}, None, 401),  # нет куки
        ({"x-refresh-token": "invalid"}, UnauthorizedError(), 401),
    ])
    async def test_refresh(self, async_client: AsyncClient, cookies, service_side_effect, expected_status):
        with patch("routers.auth.auth_service.refresh_token") as mock_refresh:
            if service_side_effect:
                mock_refresh.side_effect = service_side_effect
            else:
                mock_refresh.return_value = ("new_access", "new_refresh")

            async_client.cookies.update(cookies)
            response = await async_client.post("/auth/refresh")
            assert response.status_code == expected_status

class TestModerationRouter:
    @pytest.mark.parametrize("payload,service_side_effect,expected_status", [
        ({"item_id": 1}, None, 202),
        ({"item_id": 999}, AdvertisementNotFoundError("not found"), 404),
        ({"item_id": 1}, Exception("kafka"), 500),
    ])
    async def test_async_predict(self, async_client: AsyncClient, payload, service_side_effect, expected_status):
        with patch("routers.moderation.service.start_moderation") as mock_start:
            if service_side_effect:
                mock_start.side_effect = service_side_effect
            else:
                mock_start.return_value = MagicMock(task_id=123, status="pending", message="ok")

            response = await async_client.post("/moderation/async_predict", json=payload)
            assert response.status_code == expected_status

    @pytest.mark.parametrize("task_id,service_side_effect,expected_status", [
        (1, None, 200),
        (2, ModerationTaskNotFoundError("not found"), 404),
    ])
    async def test_get_moderation_result(self, async_client: AsyncClient, task_id, service_side_effect, expected_status):
        with patch("routers.moderation.service.get_moderation_status") as mock_get:
            if service_side_effect:
                mock_get.side_effect = service_side_effect
            else:
                mock_get.return_value = MagicMock(id=task_id, status="completed", is_violation=True, probability=0.9)

            response = await async_client.get(f"/moderation/moderation_result/{task_id}")
            assert response.status_code == expected_status