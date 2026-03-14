import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock

from services.advertisement import AdvertisementMLService
from services.auth import AuthService
from services.moderation import AsyncModerationService
from models.advertisement import AdvertisementLite, PredictionResult
from models.auth import TokenPairResponse
from models.moderation import AsyncPredictRequest, AsyncTaskStatusRequest
from errors import AdvertisementNotFoundError

pytestmark = pytest.mark.integration


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.usefixtures("run_migrations", "clean_db")
class TestAdvertisementMLServiceIntegration:
    @pytest.mark.parametrize("item_id", [1])
    async def test_simple_predict_success(self, item_id):
        from repositories.user import UserRepository
        from repositories.advertisement import AdvertisementRepository

        user_repo = UserRepository()
        user = await user_repo.create("seller", "pass1234", "s@ex.com", True)
        ad_repo = AdvertisementRepository()
        ad = await ad_repo.create(user.id, "Ad", "Desc", 1, 1)

        service = AdvertisementMLService()
        result = await service.simple_predict(AdvertisementLite(item_id=ad.id))

        assert isinstance(result, PredictionResult)
        assert isinstance(result.is_violation, bool)
        assert 0.0 <= result.probability <= 1.0

    @pytest.mark.parametrize("item_id", [9999])
    async def test_simple_predict_not_found(self, item_id):
        service = AdvertisementMLService()
        with pytest.raises(AdvertisementNotFoundError):
            await service.simple_predict(AdvertisementLite(item_id=item_id))


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.usefixtures("run_migrations", "clean_db")
class TestModerationServiceIntegration:
    @pytest.mark.parametrize("item_id", [1])
    async def test_start_and_get_moderation(self, item_id, kafka_container):
        from repositories.user import UserRepository
        from repositories.advertisement import AdvertisementRepository

        user_repo = UserRepository()
        user = await user_repo.create("seller", "pass1234", "s@ex.com", True)
        ad_repo = AdvertisementRepository()
        ad = await ad_repo.create(user.id, "Ad", "Desc", 1, 1)

        service = AsyncModerationService()
        service.producer = AsyncMock()
        service.producer.send_moderation_request = AsyncMock()

        dto = AsyncPredictRequest(item_id=ad.id)
        result = await service.start_moderation(dto)
        assert result.task_id is not None
        assert result.status == "pending"

        status_dto = AsyncTaskStatusRequest(task_id=result.task_id)
        status_result = await service.get_moderation_status(status_dto)
        assert status_result.status == "pending"

    @pytest.mark.parametrize("item_id", [9999])
    async def test_start_moderation_ad_not_found(self, item_id):
        service = AsyncModerationService()
        service.producer = AsyncMock()
        with pytest.raises(AdvertisementNotFoundError):
            await service.start_moderation(AsyncPredictRequest(item_id=item_id))


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.usefixtures("run_migrations", "clean_db")
class TestAuthServiceIntegration:
    @pytest.mark.parametrize("login,password,expected", [
        ("authuser", "validpass", True),
    ])
    async def test_login_and_refresh(self, login, password, expected):
        from repositories.account import AccountRepository

        repo = AccountRepository()
        await repo.create(login, password)

        service = AuthService()

        token_pair = await service.login(login, password)
        assert isinstance(token_pair, TokenPairResponse)
        assert token_pair.user_token is not None
        assert token_pair.refresh_token is not None

        account = await service.verify(token_pair.user_token)
        assert account.login == login

        new_token_pair = await service.refresh_token(token_pair.refresh_token)
        assert isinstance(new_token_pair, TokenPairResponse)
        assert new_token_pair.user_token != token_pair.user_token
        assert new_token_pair.refresh_token != token_pair.refresh_token