import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from services.advertisement import AdvertisementMLService
from services.auth import AuthService
from services.moderation import AsyncModerationService
from errors import (
    AdvertisementNotFoundError, ModerationTaskNotFoundError, ModelNotReadyError,
    UnauthorizedError, AuthorizedError, UserNotFoundError
)
from models.advertisement import AdvertisementLite
from models.moderation import AsyncPredictRequest, AsyncTaskStatusRequest

class TestAdvertisementMLService:
    @pytest.mark.parametrize("dto,is_violation,probability", [
        (AdvertisementLite(item_id=1), True, 0.7),
        (AdvertisementLite(item_id=2), False, 0.3),
    ])
    async def test_simple_predict_success(self, dto, is_violation, probability):
        service = AdvertisementMLService()
        # мокаем _get_model и predict, так как они синхронные
        with patch.object(service, '_get_model', return_value=MagicMock()) as mock_get_model:
            with patch.object(service, 'predict', return_value=(is_violation, probability)) as mock_predict:
                with patch.object(service.advertisement_repo, 'get_by_id_with_user', new=AsyncMock(return_value=MagicMock())):
                    result = await service.simple_predict(dto)
                    assert result == (is_violation, probability)
                    mock_predict.assert_called_once()

    @pytest.mark.parametrize("dto,exception", [
        (AdvertisementLite(item_id=999), AdvertisementNotFoundError),
        (AdvertisementLite(item_id=1), ModelNotReadyError),
    ])
    async def test_simple_predict_errors(self, dto, exception):
        service = AdvertisementMLService()
        if exception == AdvertisementNotFoundError:
            with patch.object(service.advertisement_repo, 'get_by_id_with_user', new=AsyncMock(return_value=None)):
                with pytest.raises(AdvertisementNotFoundError):
                    await service.simple_predict(dto)
        elif exception == ModelNotReadyError:
            with patch.object(service.advertisement_repo, 'get_by_id_with_user', new=AsyncMock(return_value=MagicMock())):
                with patch.object(service, '_get_model', side_effect=ModelNotReadyError):
                    with pytest.raises(ModelNotReadyError):
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
        # Используем patch для методов репозиториев на уровне классов
        with patch("services.auth.AccountRepository.get_by_login_and_password", new=AsyncMock(return_value=account)) as mock_get:
            with patch("services.auth.AuthRepository.update_refresh_token", new=AsyncMock()) as mock_update:
                service = AuthService()
                service._build_user_token = MagicMock(return_value="user_token")
                service._build_refresh_token = MagicMock(return_value="refresh_token")

                if expected_exception:
                    if account is None:
                        mock_get.side_effect = UserNotFoundError
                    with pytest.raises(expected_exception):
                        await service.login(login, password)
                else:
                    user_token, refresh_token = await service.login(login, password)
                    assert user_token == "user_token"
                    assert refresh_token == "refresh_token"
                    mock_get.assert_called_once_with(login, password)
                    mock_update.assert_called_once()

    @pytest.mark.parametrize("old_token,user_id,account,expected_exception", [
        ("valid", 1, MagicMock(is_blocked=False), None),
        ("expired", None, None, UnauthorizedError),
        ("valid", 2, MagicMock(is_blocked=True), UnauthorizedError),
    ])
    async def test_refresh_token(self, old_token, user_id, account, expected_exception):
        with patch("services.auth.AuthRepository.get_user_id_by_refresh_token", new=AsyncMock(return_value=user_id)) as mock_get_id:
            with patch("services.auth.AccountRepository.get_by_id", new=AsyncMock(return_value=account)) as mock_get_account:
                with patch("services.auth.AuthRepository.update_refresh_token", new=AsyncMock()) as mock_update:
                    service = AuthService()
                    service._build_user_token = MagicMock(return_value="new_user")
                    service._build_refresh_token = MagicMock(return_value="new_refresh")

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
                        mock_get_id.assert_called_once_with(old_token)
                        mock_get_account.assert_called_once_with(user_id)
                        mock_update.assert_called_once()

    @pytest.mark.parametrize("token,payload,account,expected", [
        ("good", {"user_id": 1, "expired_at": (datetime.now() + timedelta(hours=1)).isoformat()}, MagicMock(is_blocked=False), True),
        ("expired", {"user_id": 1, "expired_at": (datetime.now() - timedelta(hours=1)).isoformat()}, None, UnauthorizedError),
        ("bad", {}, None, UnauthorizedError),
        ("blocked", {"user_id": 1, "expired_at": (datetime.now() + timedelta(hours=1)).isoformat()}, MagicMock(is_blocked=True), UnauthorizedError),
    ])
    async def test_verify(self, token, payload, account, expected):
        # Патчим метод класса AuthService._parse_token, так как экземпляр frozen
        with patch.object(AuthService, '_parse_token', return_value=payload):
            with patch("services.auth.AccountRepository.get_by_id", new=AsyncMock(return_value=account)) as mock_get_account:
                service = AuthService()
                if expected is True:
                    result = await service.verify(token)
                    assert result == account
                else:
                    with pytest.raises(expected):
                        await service.verify(token)

class TestModerationService:
    @pytest.mark.parametrize("item_id,exists,create_result,send_ok,expected_exception", [
        (1, True, MagicMock(id=100), True, None),
        (2, False, None, False, AdvertisementNotFoundError),
        (3, True, MagicMock(id=101), False, Exception),  # ошибка Kafka
    ])
    async def test_start_moderation(self, item_id, exists, create_result, send_ok, expected_exception):
        service = AsyncModerationService()
        # мокаем репозиторий и продюсер
        with patch.object(service.repo, 'check_advertisement_exists', new=AsyncMock(return_value=exists)):
            with patch.object(service.repo, 'create_pending', new=AsyncMock(return_value=create_result)):
                with patch.object(service.producer, 'send_moderation_request', new=AsyncMock(side_effect=None if send_ok else Exception("Kafka error"))):
                    with patch.object(service.repo, 'update_result', new=AsyncMock()):
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
        with patch.object(service.repo, 'get_result_by_id', new=AsyncMock(return_value=repo_result)):
            dto = AsyncTaskStatusRequest(task_id=task_id)
            if expected_exception:
                with pytest.raises(expected_exception):
                    await service.get_moderation_status(dto)
            else:
                result = await service.get_moderation_status(dto)
                assert result.id == task_id