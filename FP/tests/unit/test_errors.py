import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient
from fastapi import status

from errors import (
    AdvertisementNotFoundError,
    UserNotFoundError,
    ModerationTaskNotFoundError,
    ModelNotReadyError,
    UnAuthorizedError,
    AuthenticationError,
)
from models.account import AccountModel


class TestExceptionClasses:

    @pytest.mark.parametrize("exc_class", [
        AdvertisementNotFoundError,
        UserNotFoundError,
        ModerationTaskNotFoundError,
        ModelNotReadyError,
        UnAuthorizedError,
        AuthenticationError,
    ])
    def test_is_exception_subclass(self, exc_class):
        assert issubclass(exc_class, Exception)

    @pytest.mark.parametrize("exc_class,message", [
        (AdvertisementNotFoundError, "Advertisement 42 not found"),
        (UserNotFoundError, "User 7 not found"),
        (ModerationTaskNotFoundError, "Task 3 not found"),
        (ModelNotReadyError, "Model not loaded"),
        (UnAuthorizedError, "Not authorized"),
        (AuthenticationError, "Bad credentials"),
    ])
    def test_can_be_raised_and_caught(self, exc_class, message):
        with pytest.raises(exc_class, match=message):
            raise exc_class(message)


class TestUserNotFoundError:

    async def test_user_repo_get_by_id_not_found_returns_none(self):
        from repositories.user import UserRepository
        repo = UserRepository()
        with patch.object(repo.redis_storage, 'get', AsyncMock(return_value=None)), \
             patch.object(repo.storage, 'get_by_id', AsyncMock(return_value=None)):
            result = await repo.get_by_id(9999)
            assert result is None

    async def test_account_repo_get_by_id_raises_user_not_found(self):
        from repositories.account import AccountRepository
        repo = AccountRepository()
        with patch.object(repo.redis_storage, 'get', AsyncMock(return_value=None)), \
             patch.object(repo.storage, 'get_by_id', AsyncMock(return_value=None)):
            with pytest.raises(UserNotFoundError):
                await repo.get_by_id(9999)

    async def test_account_repo_delete_raises_user_not_found(self):
        from repositories.account import AccountRepository
        repo = AccountRepository()
        with patch.object(repo.storage, 'delete', AsyncMock(return_value=None)), \
             patch.object(repo.redis_storage, 'delete', AsyncMock()):
            with pytest.raises(UserNotFoundError):
                await repo.delete(9999)

    async def test_account_repo_block_raises_user_not_found(self):
        from repositories.account import AccountRepository
        repo = AccountRepository()
        with patch.object(repo.storage, 'block', AsyncMock(return_value=None)), \
             patch.object(repo.redis_storage, 'delete', AsyncMock()):
            with pytest.raises(UserNotFoundError):
                await repo.block(9999)

    async def test_account_repo_get_by_login_and_password_raises_user_not_found(self):
        from repositories.account import AccountRepository
        repo = AccountRepository()
        with patch.object(repo.storage, 'get_by_login_and_password',
                          AsyncMock(return_value=None)):
            with pytest.raises(UserNotFoundError):
                await repo.get_by_login_and_password("ghost", "wrong")

    async def test_auth_service_login_converts_user_not_found_to_authorized_error(self):
        from services.auth import AuthService
        service = AuthService()
        with patch("services.auth.AccountRepository.get_by_login_and_password",
                   new=AsyncMock(side_effect=UserNotFoundError("User not found"))):
            with pytest.raises(AuthenticationError):
                await service.login("ghost", "pass")

    async def test_auth_service_verify_converts_user_not_found_to_unauthorized(self):
        from services.auth import AuthService
        payload = {
            "user_id": 999,
            "expired_at": "2099-01-01T00:00:00",
        }
        with patch.object(AuthService, '_parse_token', return_value=payload), \
             patch("services.auth.AccountRepository.get_by_id",
                   new=AsyncMock(side_effect=UserNotFoundError("User not found"))):
            service = AuthService()
            with pytest.raises(UnAuthorizedError):
                await service.verify("any_token")


class TestModerationTaskNotFoundError:

    async def test_moderation_service_raises_task_not_found(self):
        from services.moderation import AsyncModerationService
        from models.moderation import AsyncTaskStatusRequest
        service = AsyncModerationService()
        with patch.object(service.repo, 'get_result_by_id',
                          AsyncMock(return_value=None)):
            with pytest.raises(ModerationTaskNotFoundError):
                await service.get_moderation_status(
                    AsyncTaskStatusRequest(task_id=9999)
                )

    async def test_moderation_router_returns_404_on_task_not_found(
            self, async_client: AsyncClient, app):
        mock_account = AccountModel(
            id=1, login="u", password="password123", is_blocked=False
        )
        from dependencies import get_current_account, get_moderation_service
        app.dependency_overrides[get_current_account] = lambda: mock_account
        mock_svc = AsyncMock()
        mock_svc.get_moderation_status.side_effect = ModerationTaskNotFoundError(
            "Task 9999 not found"
        )
        app.dependency_overrides[get_moderation_service] = lambda: mock_svc

        response = await async_client.get("/moderation/moderation_result/9999")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        app.dependency_overrides.clear()


class TestExceptionHandlers:

    async def test_unauthorized_error_handler_returns_401(
            self, async_client: AsyncClient, app):
        from dependencies import get_current_account

        async def _raise_unauthorized():
            raise UnAuthorizedError()

        app.dependency_overrides[get_current_account] = _raise_unauthorized

        response = await async_client.post(
            "/advertisement/simple_predict", json={"item_id": 1}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["message"] == "User not authorized"
        app.dependency_overrides.clear()

    async def test_authorized_error_handler_returns_400(
            self, async_client: AsyncClient, app):
        from dependencies import auth_service
        mock_svc = AsyncMock()
        mock_svc.login.side_effect = AuthenticationError()
        app.dependency_overrides[auth_service] = lambda: mock_svc

        response = await async_client.post(
            "/auth/login", json={"login": "bad", "password": "bad"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["message"] == "Login or password is not corrected"
        app.dependency_overrides.clear()

    async def test_unauthorized_no_cookie_returns_401(
            self, async_client: AsyncClient):
        response = await async_client.post(
            "/advertisement/simple_predict", json={"item_id": 1}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_unauthorized_error_response_body_structure(
            self, async_client: AsyncClient, app):
        from dependencies import get_current_account

        async def _raise_unauthorized():
            raise UnAuthorizedError()

        app.dependency_overrides[get_current_account] = _raise_unauthorized

        response = await async_client.post(
            "/advertisement/simple_predict", json={"item_id": 1}
        )

        body = response.json()
        assert set(body.keys()) == {"message"}
        app.dependency_overrides.clear()

    async def test_authorized_error_response_body_structure(
            self, async_client: AsyncClient, app):
        from dependencies import auth_service
        mock_svc = AsyncMock()
        mock_svc.login.side_effect = AuthenticationError()
        app.dependency_overrides[auth_service] = lambda: mock_svc

        response = await async_client.post(
            "/auth/login", json={"login": "x", "password": "y"}
        )

        body = response.json()
        assert set(body.keys()) == {"message"}
        app.dependency_overrides.clear()