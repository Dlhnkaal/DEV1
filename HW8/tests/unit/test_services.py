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
from models.advertisement import (
    AdvertisementLite, AdvertisementWithUserBase, PredictionResult, ActionStatus
)
from models.moderation import AsyncPredictRequest, AsyncTaskStatusRequest
from models.auth import TokenPairResponse


class TestAdvertisementMLServicePredict:

    def _dto(self, is_verified_seller=True) -> AdvertisementWithUserBase:
        return AdvertisementWithUserBase(
            item_id=1, seller_id=1, name="Test",
            description="Some description text", category=1,
            images_qty=3, is_verified_seller=is_verified_seller
        )

    @pytest.mark.parametrize("proba,expected_violation", [
        (0.9,  True),
        (0.2,  False),
        (0.5,  False),
    ])
    async def test_predict_violation_flag(self, proba, expected_violation):
        service = AdvertisementMLService()
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = [[1 - proba, proba]]

        with patch.object(service, '_get_model', return_value=mock_model):
            result = await service.predict(self._dto())

        assert isinstance(result, PredictionResult)
        assert result.is_violation == expected_violation
        assert abs(result.probability - proba) < 1e-6

    async def test_predict_model_not_ready_raises(self):
        service = AdvertisementMLService()
        with patch.object(service, '_get_model', side_effect=ModelNotReadyError("no model")):
            with pytest.raises(ModelNotReadyError):
                await service.predict(self._dto())

    def test_load_model_failure_sets_model_to_none(self):
        service = AdvertisementMLService()
        with patch('services.advertisement.os.path.exists', return_value=True), \
             patch('services.advertisement.load_model',
                   side_effect=Exception("corrupt file")):
            with pytest.raises(Exception, match="corrupt file"):
                service._load_model()

        assert service._model is None
        assert service._model_loaded is False

    def test_get_model_raises_model_not_ready_when_model_stays_none(self):
        service = AdvertisementMLService()
        service._model = None

        with patch.object(service, '_load_model', return_value=None):
            with pytest.raises(ModelNotReadyError):
                service._get_model()

    async def test_predict_propagates_model_not_ready_for_503(self):
        service = AdvertisementMLService()
        service._model = None

        with patch.object(service, '_load_model', return_value=None):
            with pytest.raises(ModelNotReadyError):
                await service.predict(self._dto())

    def test_load_model_trains_when_file_missing(self):
        service = AdvertisementMLService()
        mock_model = MagicMock()

        with patch('services.advertisement.os.path.exists', return_value=False), \
             patch('ml.model.train_model', return_value=mock_model) as mock_train, \
             patch('ml.model.save_model'):
            service._load_model()

        mock_train.assert_called_once()
        assert service._model is mock_model


class TestAdvertisementMLServiceSimplePredict:

    @pytest.mark.parametrize("is_violation,probability", [
        (True,  0.7),
        (False, 0.3),
    ])
    async def test_simple_predict_success(self, is_violation, probability):
        service = AdvertisementMLService()
        mock_ad = MagicMock()
        expected_result = PredictionResult(
            is_violation=is_violation, probability=probability
        )
        with patch.object(service.advertisement_repo, 'get_by_id_with_user',
                          new=AsyncMock(return_value=mock_ad)), \
             patch.object(service, 'predict',
                          new=AsyncMock(return_value=expected_result)) as mock_predict:
            result = await service.simple_predict(AdvertisementLite(item_id=1))

        assert isinstance(result, PredictionResult)
        assert result.is_violation == is_violation
        assert result.probability == probability
        mock_predict.assert_awaited_once_with(mock_ad)

    async def test_simple_predict_advertisement_not_found(self):
        service = AdvertisementMLService()
        with patch.object(service.advertisement_repo, 'get_by_id_with_user',
                          new=AsyncMock(return_value=None)):
            with pytest.raises(AdvertisementNotFoundError):
                await service.simple_predict(AdvertisementLite(item_id=9999))

    async def test_simple_predict_model_not_ready(self):
        service = AdvertisementMLService()
        with patch.object(service.advertisement_repo, 'get_by_id_with_user',
                          new=AsyncMock(return_value=MagicMock())), \
             patch.object(service, 'predict',
                          new=AsyncMock(side_effect=ModelNotReadyError())):
            with pytest.raises(ModelNotReadyError):
                await service.simple_predict(AdvertisementLite(item_id=1))

    @pytest.mark.parametrize("item_id", [1, 2])
    async def test_close_advertisement(self, item_id):
        service = AdvertisementMLService()
        service.moderation_repo.get_task_ids_by_item_id = AsyncMock(
            return_value=MagicMock(task_ids=[10, 11])
        )
        service.moderation_repo.delete_cache = AsyncMock()
        service.advertisement_repo.close = AsyncMock(
            return_value=ActionStatus(success=True)
        )
        result = await service.close_advertisement(MagicMock(item_id=item_id))

        assert isinstance(result, ActionStatus)
        assert result.success is True
        service.moderation_repo.delete_cache.assert_any_call(10)
        service.moderation_repo.delete_cache.assert_any_call(11)


class TestAuthService:

    @pytest.mark.parametrize("login,password,account,expected_exception", [
        ("user",    "pass", MagicMock(id=1, is_blocked=False), None),
        ("user",    "wrong", None,                              AuthorizedError),
        ("blocked", "pass", MagicMock(id=2, is_blocked=True),  AuthorizedError),
    ])
    async def test_login(self, login, password, account, expected_exception):
        with patch("services.auth.AccountRepository.get_by_login_and_password",
                   new=AsyncMock(return_value=account)) as mock_get, \
             patch("services.auth.AuthRepository.update_refresh_token",
                   new=AsyncMock()):
            service = AuthService()
            service._build_user_token  = MagicMock(return_value="user_token")
            service._build_refresh_token = MagicMock(return_value="refresh_token")

            if expected_exception:
                if account is None:
                    mock_get.side_effect = UserNotFoundError
                with pytest.raises(expected_exception):
                    await service.login(login, password)
            else:
                result = await service.login(login, password)
                assert isinstance(result, TokenPairResponse)
                assert result.user_token   == "user_token"
                assert result.refresh_token == "refresh_token"

    @pytest.mark.parametrize("old_token,user_id,account,expected_exception", [
        ("valid",   1,    MagicMock(id=1, is_blocked=False), None),
        ("expired", None, None,                               UnauthorizedError),
        ("valid",   2,    MagicMock(id=2, is_blocked=True),  UnauthorizedError),
    ])
    async def test_refresh_token(self, old_token, user_id, account, expected_exception):
        from models.auth import UserIdResponse
        with patch("services.auth.AuthRepository.get_user_id_by_refresh_token",
                   new=AsyncMock(return_value=UserIdResponse(user_id=user_id))), \
             patch("services.auth.AccountRepository.get_by_id",
                   new=AsyncMock(return_value=account)), \
             patch("services.auth.AuthRepository.update_refresh_token",
                   new=AsyncMock()):
            service = AuthService()
            service._build_user_token    = MagicMock(return_value="new_user")
            service._build_refresh_token = MagicMock(return_value="new_refresh")

            if expected_exception:
                with pytest.raises(UnauthorizedError):
                    await service.refresh_token(old_token)
            else:
                result = await service.refresh_token(old_token)
                assert isinstance(result, TokenPairResponse)
                assert result.user_token    == "new_user"
                assert result.refresh_token == "new_refresh"

    @pytest.mark.parametrize("token,payload,account,expected", [
        (
            "good",
            {"user_id": 1, "expired_at": (datetime.now() + timedelta(hours=1)).isoformat()},
            MagicMock(id=1, is_blocked=False),
            True,
        ),
        (
            "expired",
            {"user_id": 1, "expired_at": (datetime.now() - timedelta(hours=1)).isoformat()},
            None,
            UnauthorizedError,
        ),
        ("bad", {}, None, UnauthorizedError),
        (
            "blocked",
            {"user_id": 1, "expired_at": (datetime.now() + timedelta(hours=1)).isoformat()},
            MagicMock(id=1, is_blocked=True),
            UnauthorizedError,
        ),
    ])
    async def test_verify(self, token, payload, account, expected):
        with patch.object(AuthService, '_parse_token', return_value=payload), \
             patch("services.auth.AccountRepository.get_by_id",
                   new=AsyncMock(return_value=account)):
            service = AuthService()
            if expected is True:
                result = await service.verify(token)
                assert result == account
            else:
                with pytest.raises(expected):
                    await service.verify(token)


class TestModerationService:

    @pytest.mark.parametrize("item_id,exists,create_result,send_ok,expected_exception", [
        (1, True,  MagicMock(id=100), True,  None),
        (2, False, None,              False, AdvertisementNotFoundError),
        (3, True,  MagicMock(id=101), False, Exception),
    ])
    async def test_start_moderation(self, item_id, exists, create_result,
                                    send_ok, expected_exception):
        service = AsyncModerationService()
        with patch.object(service.repo, 'check_advertisement_exists',
                          new=AsyncMock(return_value=exists)), \
             patch.object(service.repo, 'create_pending',
                          new=AsyncMock(return_value=create_result)), \
             patch.object(service.producer, 'send_moderation_request',
                          new=AsyncMock(
                              side_effect=None if send_ok else Exception("Kafka error")
                          )), \
             patch.object(service.repo, 'update_result',
                          new=AsyncMock()) as mock_update:
            dto = AsyncPredictRequest(item_id=item_id)
            if expected_exception:
                with pytest.raises(expected_exception):
                    await service.start_moderation(dto)
                if exists and not send_ok and create_result:
                    mock_update.assert_awaited_once()
            else:
                result = await service.start_moderation(dto)
                assert result.task_id == create_result.id
                assert result.status  == "pending"

    @pytest.mark.parametrize("task_id,repo_result,expected_exception", [
        (1, MagicMock(id=1), None),
        (2, None,            ModerationTaskNotFoundError),
    ])
    async def test_get_moderation_status(self, task_id, repo_result, expected_exception):
        service = AsyncModerationService()
        with patch.object(service.repo, 'get_result_by_id',
                          new=AsyncMock(return_value=repo_result)):
            dto = AsyncTaskStatusRequest(task_id=task_id)
            if expected_exception:
                with pytest.raises(expected_exception):
                    await service.get_moderation_status(dto)
            else:
                result = await service.get_moderation_status(dto)
                assert result.id == task_id