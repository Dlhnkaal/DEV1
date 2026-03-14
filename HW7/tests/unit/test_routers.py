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
from dependencies import get_current_account
from models.account import AccountModel

@pytest.fixture
def mock_account():
    return AccountModel(id=1, login="testuser", password="hashedpass", is_blocked=False)

@pytest.mark.usefixtures("mock_current_account")
class TestAdvertisementRouter:
    @pytest.mark.parametrize("payload,status_code,response_body", [
        ({"seller_id": 1, "name": "Test", "description": "desc", "category": 1, "images_qty": 5, "item_id": 10, "is_verified_seller": True}, 200, {"is_violation": True, "probability": 0.8}),
        ({"seller_id": 1, "name": "Test", "description": "desc", "category": 1, "images_qty": 5, "item_id": 10, "is_verified_seller": True}, 503, None),
    ])
    async def test_predict(self, async_client: AsyncClient, app, payload, status_code, response_body, mock_account):
        # Подменяем зависимость get_current_account
        app.dependency_overrides[get_current_account] = lambda: mock_account
        
        mock_service = AsyncMock()
        if status_code == 200:
            mock_service.predict.return_value = (response_body["is_violation"], response_body["probability"])
        else:
            mock_service.predict.side_effect = ModelNotReadyError()

        # Подменяем зависимость get_ml_service
        from dependencies import get_ml_service
        app.dependency_overrides[get_ml_service] = lambda: mock_service

        response = await async_client.post("/advertisement/predict", json=payload)
        assert response.status_code == status_code
        if status_code == 200:
            assert response.json() == response_body

        # Очищаем overrides после теста
        app.dependency_overrides.clear()

    @pytest.mark.parametrize("payload,status_code,exception", [
        ({"item_id": 1}, 200, None),
        ({"item_id": 999}, 404, AdvertisementNotFoundError),
    ])
    async def test_simple_predict(self, async_client: AsyncClient, app, payload, status_code, exception, mock_account):
        app.dependency_overrides[get_current_account] = lambda: mock_account
        
        mock_service = AsyncMock()
        if exception:
            mock_service.simple_predict.side_effect = exception("Not found")
        else:
            mock_service.simple_predict.return_value = (True, 0.9)

        from dependencies import get_ml_service
        app.dependency_overrides[get_ml_service] = lambda: mock_service

        response = await async_client.post("/advertisement/simple_predict", json=payload)
        assert response.status_code == status_code

        app.dependency_overrides.clear()

    @pytest.mark.parametrize("payload,close_success,status_code", [
        ({"item_id": 1}, True, 200),
        ({"item_id": 2}, False, 404),
    ])
    async def test_close_advertisement(self, async_client: AsyncClient, app, payload, close_success, status_code, mock_account):
        app.dependency_overrides[get_current_account] = lambda: mock_account
        
        mock_service = AsyncMock()
        mock_service.close_advertisement.return_value = close_success

        from dependencies import get_ml_service
        app.dependency_overrides[get_ml_service] = lambda: mock_service

        response = await async_client.post("/advertisement/close", json=payload)
        assert response.status_code == status_code

        app.dependency_overrides.clear()

class TestAuthRouter:
    @pytest.mark.parametrize("login,password,service_side_effect,expected_status", [
        ("user", "pass", None, 200),
        ("user", "wrong", AuthorizedError(), 400),
    ])
    async def test_login(self, async_client: AsyncClient, app, login, password, service_side_effect, expected_status):
        mock_service = AsyncMock()
        if service_side_effect:
            mock_service.login.side_effect = service_side_effect
        else:
            mock_service.login.return_value = ("access", "refresh")

        from dependencies import auth_service
        app.dependency_overrides[auth_service] = lambda: mock_service

        response = await async_client.post("/auth/login", json={"login": login, "password": password})
        assert response.status_code == expected_status

        app.dependency_overrides.clear()

    @pytest.mark.parametrize("cookies,service_side_effect,expected_status", [
        ({"x-refresh-token": "old"}, None, 200),
        ({}, None, 401),
        ({"x-refresh-token": "invalid"}, UnauthorizedError(), 401),
    ])
    async def test_refresh(self, async_client: AsyncClient, app, cookies, service_side_effect, expected_status):
        mock_service = AsyncMock()
        if service_side_effect:
            mock_service.refresh_token.side_effect = service_side_effect
        else:
            mock_service.refresh_token.return_value = ("new_access", "new_refresh")

        from dependencies import auth_service
        app.dependency_overrides[auth_service] = lambda: mock_service

        async_client.cookies.update(cookies)
        response = await async_client.post("/auth/refresh")
        assert response.status_code == expected_status

        app.dependency_overrides.clear()

class TestModerationRouter:
    @pytest.mark.parametrize("payload,service_side_effect,expected_status", [
        ({"item_id": 1}, None, 202),
        ({"item_id": 999}, AdvertisementNotFoundError("not found"), 404),
        ({"item_id": 1}, Exception("kafka"), 500),
    ])
    async def test_async_predict(self, async_client: AsyncClient, app, payload, service_side_effect, expected_status, mock_account):
        app.dependency_overrides[get_current_account] = lambda: mock_account
        
        mock_service = AsyncMock()
        if service_side_effect:
            mock_service.start_moderation.side_effect = service_side_effect
        else:
            mock_service.start_moderation.return_value = MagicMock(task_id=123, status="pending", message="ok")

        from dependencies import get_moderation_service
        app.dependency_overrides[get_moderation_service] = lambda: mock_service

        response = await async_client.post("/moderation/async_predict", json=payload)
        assert response.status_code == expected_status

        app.dependency_overrides.clear()

    @pytest.mark.parametrize("task_id,service_side_effect,expected_status", [
        (1, None, 200),
        (2, ModerationTaskNotFoundError("not found"), 404),
    ])
    async def test_get_moderation_result(self, async_client: AsyncClient, app, task_id, service_side_effect, expected_status, mock_account):
        app.dependency_overrides[get_current_account] = lambda: mock_account
        
        mock_service = AsyncMock()
        if service_side_effect:
            mock_service.get_moderation_status.side_effect = service_side_effect
        else:
            mock_service.get_moderation_status.return_value = MagicMock(id=task_id, status="completed", is_violation=True, probability=0.9)

        from dependencies import get_moderation_service
        app.dependency_overrides[get_moderation_service] = lambda: mock_service

        response = await async_client.get(f"/moderation/moderation_result/{task_id}")
        assert response.status_code == expected_status

        app.dependency_overrides.clear()