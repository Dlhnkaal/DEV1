import pytest
import pytest_asyncio
from services.advertisement import AdvertisementMLService
from services.auth import AuthService
from services.moderation import AsyncModerationService
from models.advertisement import AdvertisementLite
from models.moderation import AsyncPredictRequest, AsyncTaskStatusRequest
from errors import AdvertisementNotFoundError

pytestmark = pytest.mark.integration

@pytest.mark.usefixtures("run_migrations", "clean_db")
class TestAdvertisementMLServiceIntegration:
    @pytest.mark.parametrize("item_id", [1])
    async def test_simple_predict_success(self, item_id):
        # создаём пользователя и объявление
        from repositories.user import UserRepository
        from repositories.advertisement import AdvertisementRepository
        user_repo = UserRepository()
        user = await user_repo.create("seller", "pass1234", "s@ex.com", True)
        ad_repo = AdvertisementRepository()
        ad = await ad_repo.create(user.id, "Ad", "Desc", 1, 1)

        service = AdvertisementMLService()
        result = await service.simple_predict(AdvertisementLite(item_id=ad.id))
        assert isinstance(result[0], bool)
        assert 0 <= result[1] <= 1

    @pytest.mark.parametrize("item_id", [9999])
    async def test_simple_predict_not_found(self, item_id):
        service = AdvertisementMLService()
        with pytest.raises(AdvertisementNotFoundError):
            await service.simple_predict(AdvertisementLite(item_id=item_id))

@pytest.mark.usefixtures("run_migrations", "clean_db")
class TestModerationServiceIntegration:
    @pytest.mark.parametrize("item_id", [1])
    async def test_start_and_get_moderation(self, item_id, kafka_container):
        # создаём пользователя и объявление
        from repositories.user import UserRepository
        from repositories.advertisement import AdvertisementRepository
        user_repo = UserRepository()
        user = await user_repo.create("seller", "pass1234", "s@ex.com", True)
        ad_repo = AdvertisementRepository()
        ad = await ad_repo.create(user.id, "Ad", "Desc", 1, 1)

        os.environ["KAFKA_BOOTSTRAP"] = kafka_container.get_bootstrap_server()
        service = AsyncModerationService()
        await service.start()
        dto = AsyncPredictRequest(item_id=ad.id)
        result = await service.start_moderation(dto)
        assert result.task_id is not None
        assert result.status == "pending"

        status_dto = AsyncTaskStatusRequest(task_id=result.task_id)
        status = await service.get_moderation_status(status_dto)
        assert status.status == "pending"  # воркер не запущен

        await service.close()

    @pytest.mark.parametrize("item_id", [9999])
    async def test_start_moderation_ad_not_found(self, item_id):
        service = AsyncModerationService()
        with pytest.raises(AdvertisementNotFoundError):
            await service.start_moderation(AsyncPredictRequest(item_id=item_id))

@pytest.mark.usefixtures("run_migrations", "clean_db")
class TestAuthServiceIntegration:
    @pytest.mark.parametrize("login,password,expected", [
        ("authuser", "validpass", True),
    ])
    async def test_login_and_refresh(self, login, password, expected):
        # создаём аккаунт
        from repositories.account import AccountRepository
        repo = AccountRepository()
        await repo.create(login, password)

        service = AuthService()
        access, refresh = await service.login(login, password)
        assert access is not None
        assert refresh is not None

        account = await service.verify(access)
        assert account.login == login

        new_access, new_refresh = await service.refresh_token(refresh)
        assert new_access != access
        assert new_refresh != refresh