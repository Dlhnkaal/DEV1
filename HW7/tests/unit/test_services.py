import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.advertisement import AdvertisementMLService
from services.auth import AuthService
from services.moderation import AsyncModerationService
from errors import (
    AdvertisementNotFoundError,
    AuthorizedError,
    UnauthorizedError,
    ModerationTaskNotFoundError,
    ModelNotReadyError,
)
from models.advertisement import AdvertisementLite, AdvertisementWithUserBase
from models.moderation import AsyncPredictRequest, AsyncTaskStatusRequest
from datetime import datetime, timedelta

class TestAdvertisementMLService:
    @pytest.mark.parametrize("dto,is_violation,probability", [
        (AdvertisementLite(item_id=1), True, 0.7),
        (AdvertisementLite(item_id=2), False, 0.3),
    ])
    async def test_simple_predict_success(self, dto, is_violation, probability):
        service = AdvertisementMLService()
        service._get_model = MagicMock()
        service.predict = MagicMock(return_value=(is_violation, probability))
        service.advertisement_repo.get_by_id_with_user = AsyncMock(return_value=MagicMock())

        result = await service.simple_predict(dto)
        assert result == (is_violation, probability)

    @pytest.mark.parametrize("dto,exception", [
        (AdvertisementLite(item_id=999), AdvertisementNotFoundError),
        (AdvertisementLite(item_id=1), ModelNotReadyError),
    ])
    async def test_simple_predict_errors(self, dto, exception):
        service = AdvertisementMLService()
        if exception == AdvertisementNotFoundError:
            service.advertisement_repo.get_by_id_with_user = AsyncMock(return_value=None)
        elif exception == ModelNotReadyError:
            service.advertisement_repo.get_by_id_with_user = AsyncMock(return_value=MagicMock())
            service._get_model = MagicMock(side_effect=ModelNotReadyError)

        with pytest.raises(exception):
            await service.simple_predict(dto)

    @pytest.mark.parametrize("item_id,close_success", [
        (1, True),
        (2, False),
    ])
    async def test_close_advertisement(self, item_id, close_success):
        service = AdvertisementMLService()
        service.moderation_repo.get_task_ids_by_item_id = AsyncMock(return_value=MagicMock(task_ids=[10, 11]))
        service.moderation_repo.delete_cache = AsyncMock()
        service.advertisement_repo.close = AsyncMock(return_value=close_success)

        dto = MagicMock(item_id=item_id)
        result = await service.close_advertisement(dto)
        assert result == close_success
        service.moderation_repo.delete_cache.assert_any_call(10)
        service.moderation_repo.delete_cache.assert_any_call(11)

class TestAuthService:
    @pytest.mark.parametrize("login,password,account,expected_exception", [
        ("user", "pass", MagicMock(is_blocked=False), None),
        ("user", "wrong", None, AuthorizedError),
        ("blocked", "pass", MagicMock(is_blocked=True), AuthorizedError),
    ])
    async def test_login(self, login, password, account, expected_exception):
        service = AuthService()
        service.account_repo.get_by_login_and_password = AsyncMock(return_value=account)
        service.auth_repo.update_refresh_token = AsyncMock()
        service._build_user_token = MagicMock(return_value="user_token")
        service._build_refresh_token = MagicMock(return_value="refresh_token")

        if expected_exception:
            if account is None:
                service.account_repo.get_by_login_and_password.side_effect = UserNotFoundError
            with pytest.raises(expected_exception):
                await service.login(login, password)
        else:
            user_token, refresh_token = await service.login(login, password)
            assert user_token == "user_token"
            assert refresh_token == "refresh_token"

    @pytest.mark.parametrize("old_token,user_id,account,expected_exception", [
        ("valid", 1, MagicMock(is_blocked=False), None),
        ("expired", None, None, UnauthorizedError),
        ("valid", 2, MagicMock(is_blocked=True), UnauthorizedError),
    ])
    async def test_refresh_token(self, old_token, user_id, account, expected_exception):
        service = AuthService()
        service.auth_repo.get_user_id_by_refresh_token = AsyncMock(return_value=user_id)
        service.account_repo.get_by_id = AsyncMock(return_value=account)
        service._build_user_token = MagicMock(return_value="new_user")
        service._build_refresh_token = MagicMock(return_value="new_refresh")
        service.auth_repo.update_refresh_token = AsyncMock()

        if expected_exception:
            if not user_id:
                with pytest.raises(UnauthorizedError):
                    await service.refresh_token(old_token)
            else:
                with pytest.raises(UnauthorizedError):
                    await service.refresh_token(old_token)
        else:
            user_token, new_refresh = await service.refresh_token(old_token)
            assert user_token == "new_user"
            assert new_refresh == "new_refresh"

    @pytest.mark.parametrize("token,payload,account,expected", [
        ("good", {"user_id": 1, "expired_at": (datetime.now() + timedelta(hours=1)).isoformat()}, MagicMock(is_blocked=False), True),
        ("expired", {"user_id": 1, "expired_at": (datetime.now() - timedelta(hours=1)).isoformat()}, None, UnauthorizedError),
        ("bad", {}, None, UnauthorizedError),
        ("blocked", {"user_id": 1, "expired_at": (datetime.now() + timedelta(hours=1)).isoformat()}, MagicMock(is_blocked=True), UnauthorizedError),
    ])
    async def test_verify(self, token, payload, account, expected):
        service = AuthService()
        service._parse_token = MagicMock(return_value=payload)
        if account is not None:
            service.account_repo.get_by_id = AsyncMock(return_value=account)
        else:
            service.account_repo.get_by_id = AsyncMock(side_effect=UserNotFoundError)

        if expected is UnauthorizedError:
            with pytest.raises(UnauthorizedError):
                await service.verify(token)
        else:
            result = await service.verify(token)
            assert result == account

class TestModerationService:
    @pytest.mark.parametrize("item_id,exists,create_result,send_ok,expected_exception", [
        (1, True, MagicMock(id=100), True, None),
        (2, False, None, False, AdvertisementNotFoundError),
        (3, True, MagicMock(id=101), False, Exception),  # ошибка Kafka
    ])
    async def test_start_moderation(self, item_id, exists, create_result, send_ok, expected_exception):
        service = AsyncModerationService()
        service.repo.check_advertisement_exists = AsyncMock(return_value=exists)
        service.repo.create_pending = AsyncMock(return_value=create_result)
        service.producer.send_moderation_request = AsyncMock() if send_ok else AsyncMock(side_effect=Exception("Kafka error"))
        service.repo.update_result = AsyncMock()

        dto = AsyncPredictRequest(item_id=item_id)

        if expected_exception:
            with pytest.raises(expected_exception):
                await service.start_moderation(dto)
            if exists and not send_ok and create_result:
                service.repo.update_result.assert_awaited_once()
        else:
            result = await service.start_moderation(dto)
            assert result.task_id == create_result.id
            assert result.status == "pending"

    @pytest.mark.parametrize("task_id,repo_result,expected_exception", [
        (1, MagicMock(id=1), None),
        (2, None, ModerationTaskNotFoundError),
    ])
    async def test_get_moderation_status(self, task_id, repo_result, expected_exception):
        service = AsyncModerationService()
        service.repo.get_result_by_id = AsyncMock(return_value=repo_result)
        dto = AsyncTaskStatusRequest(task_id=task_id)

        if expected_exception:
            with pytest.raises(expected_exception):
                await service.get_moderation_status(dto)
        else:
            result = await service.get_moderation_status(dto)
            assert result.id == task_id