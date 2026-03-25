import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock
from fastapi import status

from errors import (
    AdvertisementNotFoundError,
    AuthenticationError,
    UnAuthorizedError,
    ModerationTaskNotFoundError,
    ModelNotReadyError,
)
from dependencies import get_current_account
from models.account import AccountModel
from models.advertisement import PredictionResult, ActionStatus
from models.auth import TokenPairResponse


@pytest.fixture
def mock_account():
    return AccountModel(id=1, login="testuser", password="hashedpass", is_blocked=False)


class TestAdvertisementRouterPredict:

    _VALID_PAYLOAD = {
        "seller_id": 1, "name": "Test", "description": "desc",
        "category": 1, "images_qty": 5,
        "item_id": 10, "is_verified_seller": True,
    }

    @pytest.mark.parametrize("is_violation,probability", [
        (True, 0.8),
        (False, 0.2),
    ])
    async def test_predict_success(self, async_client: AsyncClient, app,
                                   is_violation, probability, mock_account):
        app.dependency_overrides[get_current_account] = lambda: mock_account
        mock_svc = AsyncMock()
        mock_svc.predict.return_value = PredictionResult(
            is_violation=is_violation, probability=probability
        )
        from dependencies import get_ml_service
        app.dependency_overrides[get_ml_service] = lambda: mock_svc

        response = await async_client.post("/advertisement/predict",
                                           json=self._VALID_PAYLOAD)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_violation"] == is_violation
        assert data["probability"] == probability

        app.dependency_overrides.clear()

    async def test_predict_model_unavailable_returns_503(self, async_client: AsyncClient,
                                                          app, mock_account):
        app.dependency_overrides[get_current_account] = lambda: mock_account
        mock_svc = AsyncMock()
        mock_svc.predict.side_effect = ModelNotReadyError("model not loaded")
        from dependencies import get_ml_service
        app.dependency_overrides[get_ml_service] = lambda: mock_svc

        response = await async_client.post("/advertisement/predict",
                                           json=self._VALID_PAYLOAD)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        app.dependency_overrides.clear()

    @pytest.mark.parametrize("bad_payload", [
        {"seller_id": -1, "name": "T", "description": "d",
         "category": 1, "images_qty": 1, "item_id": 1, "is_verified_seller": True},
        {"seller_id": 1, "name": "", "description": "d",
         "category": 1, "images_qty": 1, "item_id": 1, "is_verified_seller": True},
        {"seller_id": 1, "name": "T", "description": "d",
         "category": 1, "images_qty": 99, "item_id": 1, "is_verified_seller": True},
        {"seller_id": 1, "name": "T", "description": "d",
         "category": 1, "images_qty": 1, "item_id": 0, "is_verified_seller": True},
    ])
    async def test_predict_invalid_input_returns_422(self, async_client: AsyncClient,
                                                      app, bad_payload, mock_account):
        app.dependency_overrides[get_current_account] = lambda: mock_account
        from dependencies import get_ml_service
        app.dependency_overrides[get_ml_service] = lambda: AsyncMock()

        response = await async_client.post("/advertisement/predict", json=bad_payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        app.dependency_overrides.clear()

    async def test_predict_requires_auth(self, async_client: AsyncClient):
        response = await async_client.post("/advertisement/predict",
                                           json=self._VALID_PAYLOAD)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAdvertisementRouterSimplePredict:

    async def test_simple_predict_success(self, async_client: AsyncClient,
                                          app, mock_account):
        app.dependency_overrides[get_current_account] = lambda: mock_account
        mock_svc = AsyncMock()
        mock_svc.simple_predict.return_value = PredictionResult(
            is_violation=True, probability=0.9
        )
        from dependencies import get_ml_service
        app.dependency_overrides[get_ml_service] = lambda: mock_svc

        response = await async_client.post("/advertisement/simple_predict",
                                           json={"item_id": 1})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_violation"] is True
        app.dependency_overrides.clear()

    async def test_simple_predict_not_found_returns_404(self, async_client: AsyncClient,
                                                         app, mock_account):
        app.dependency_overrides[get_current_account] = lambda: mock_account
        mock_svc = AsyncMock()
        mock_svc.simple_predict.side_effect = AdvertisementNotFoundError("not found")
        from dependencies import get_ml_service
        app.dependency_overrides[get_ml_service] = lambda: mock_svc

        response = await async_client.post("/advertisement/simple_predict",
                                           json={"item_id": 9999})

        assert response.status_code == status.HTTP_404_NOT_FOUND
        app.dependency_overrides.clear()

    @pytest.mark.parametrize("payload", [
        {"item_id": 0},
        {"item_id": -5},
        {},
    ])
    async def test_simple_predict_invalid_input_returns_422(self,
                                                             async_client: AsyncClient,
                                                             app, payload, mock_account):
        app.dependency_overrides[get_current_account] = lambda: mock_account
        from dependencies import get_ml_service
        app.dependency_overrides[get_ml_service] = lambda: AsyncMock()

        response = await async_client.post("/advertisement/simple_predict", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        app.dependency_overrides.clear()

    async def test_simple_predict_model_unavailable_returns_503(self,
                                                                  async_client: AsyncClient,
                                                                  app, mock_account):
        app.dependency_overrides[get_current_account] = lambda: mock_account
        mock_svc = AsyncMock()
        mock_svc.simple_predict.side_effect = ModelNotReadyError()
        from dependencies import get_ml_service
        app.dependency_overrides[get_ml_service] = lambda: mock_svc

        response = await async_client.post("/advertisement/simple_predict",
                                           json={"item_id": 1})

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        app.dependency_overrides.clear()


class TestAdvertisementRouterClose:

    @pytest.mark.parametrize("close_success,expected_status", [
        (True, 200),
        (False, 404),
    ])
    async def test_close_advertisement(self, async_client: AsyncClient, app,
                                       close_success, expected_status, mock_account):
        app.dependency_overrides[get_current_account] = lambda: mock_account
        mock_svc = AsyncMock()
        mock_svc.close_advertisement.return_value = ActionStatus(success=close_success)
        from dependencies import get_ml_service
        app.dependency_overrides[get_ml_service] = lambda: mock_svc

        response = await async_client.post("/advertisement/close", json={"item_id": 1})

        assert response.status_code == expected_status
        app.dependency_overrides.clear()


class TestAuthRouter:

    @pytest.mark.parametrize("login,password,side_effect,expected_status", [
        ("user", "pass", None, 200),
        ("user", "wrong", AuthenticationError(), 400),
    ])
    async def test_login(self, async_client: AsyncClient, app, login, password,
                         side_effect, expected_status):
        mock_svc = AsyncMock()
        if side_effect:
            mock_svc.login.side_effect = side_effect
        else:
            mock_svc.login.return_value = TokenPairResponse(
                user_token="access", refresh_token="refresh"
            )
        from dependencies import auth_service
        app.dependency_overrides[auth_service] = lambda: mock_svc

        response = await async_client.post("/auth/login",
                                           json={"login": login, "password": password})

        assert response.status_code == expected_status
        app.dependency_overrides.clear()

    @pytest.mark.parametrize("cookies,side_effect,expected_status", [
        ({"x-refresh-token": "old"}, None, 200),
        ({}, None, 401),
        ({"x-refresh-token": "bad"}, UnAuthorizedError(), 401),
    ])
    async def test_refresh(self, async_client: AsyncClient, app,
                           cookies, side_effect, expected_status):
        mock_svc = AsyncMock()
        if side_effect:
            mock_svc.refresh_token.side_effect = side_effect
        else:
            mock_svc.refresh_token.return_value = TokenPairResponse(
                user_token="new_access", refresh_token="new_refresh"
            )
        from dependencies import auth_service
        app.dependency_overrides[auth_service] = lambda: mock_svc

        async_client.cookies.update(cookies)
        response = await async_client.post("/auth/refresh")

        assert response.status_code == expected_status
        app.dependency_overrides.clear()


class TestModerationRouter:

    @pytest.mark.parametrize("payload,side_effect,expected_status", [
        ({"item_id": 1}, None, 202),
        ({"item_id": 999}, AdvertisementNotFoundError("not found"), 404),
        ({"item_id": 1}, Exception("kafka"), 500),
    ])
    async def test_async_predict(self, async_client: AsyncClient, app, payload,
                                 side_effect, expected_status, mock_account):
        app.dependency_overrides[get_current_account] = lambda: mock_account
        mock_svc = AsyncMock()
        if side_effect:
            mock_svc.start_moderation.side_effect = side_effect
        else:
            mock_svc.start_moderation.return_value = MagicMock(
                task_id=123, status="pending", message="ok"
            )
        from dependencies import get_moderation_service
        app.dependency_overrides[get_moderation_service] = lambda: mock_svc

        response = await async_client.post("/moderation/async_predict", json=payload)

        assert response.status_code == expected_status
        app.dependency_overrides.clear()

    @pytest.mark.parametrize("task_id,side_effect,expected_status", [
        (1, None, 200),
        (2, ModerationTaskNotFoundError("not found"), 404),
    ])
    async def test_get_moderation_result(self, async_client: AsyncClient, app,
                                         task_id, side_effect, expected_status,
                                         mock_account):
        app.dependency_overrides[get_current_account] = lambda: mock_account
        mock_svc = AsyncMock()
        if side_effect:
            mock_svc.get_moderation_status.side_effect = side_effect
        else:
            mock_svc.get_moderation_status.return_value = MagicMock(
                id=task_id, status="completed", is_violation=True, probability=0.9
            )
        from dependencies import get_moderation_service
        app.dependency_overrides[get_moderation_service] = lambda: mock_svc

        response = await async_client.get(f"/moderation/moderation_result/{task_id}")

        assert response.status_code == expected_status
        app.dependency_overrides.clear()