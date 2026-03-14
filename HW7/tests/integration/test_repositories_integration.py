import pytest
import pytest_asyncio
from datetime import datetime
from repositories.advertisement import AdvertisementRepository
from repositories.moderation import ModerationRepository
from repositories.user import UserRepository
from repositories.account import AccountRepository
from models.advertisement import AdvertisementInDB
from models.user import UserInDB
from models.account import AccountModel
from errors import UserNotFoundError

pytestmark = pytest.mark.integration

@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.usefixtures("clean_db")
class TestAdvertisementRepositoryIntegration:
    @pytest.mark.parametrize("seller_id,name,desc,category,img_qty", [
        (1, "Ad1", "Desc", 1, 1),
    ])
    async def test_create_and_get(self, seller_id, name, desc, category, img_qty):
        user_repo = UserRepository()
        user = await user_repo.create("seller", "password123", "s@ex.com", True)
        repo = AdvertisementRepository()
        created = await repo.create(seller_id, name, desc, category, img_qty)
        assert created.id is not None
        fetched = await repo.get_by_id_with_user(created.id)
        assert fetched is not None
        assert fetched.name == name

    @pytest.mark.parametrize("item_id", [9999])
    async def test_get_not_found(self, item_id):
        repo = AdvertisementRepository()
        fetched = await repo.get_by_id_with_user(item_id)
        assert fetched is None

    @pytest.mark.parametrize("item_id,expected", [
        (1, True),
        (999, False),
    ])
    async def test_close(self, item_id, expected):
        user_repo = UserRepository()
        user = await user_repo.create("seller", "password123", "s@ex.com", True)
        ad_repo = AdvertisementRepository()
        ad = await ad_repo.create(user.id, "Ad", "Desc", 1, 1)
        result = await ad_repo.close(ad.id if item_id == 1 else 999)
        assert result.success == expected


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.usefixtures("clean_db")
class TestModerationRepositoryIntegration:
    @pytest.mark.parametrize("item_id", [1])
    async def test_create_pending_and_get(self, item_id):
        user_repo = UserRepository()
        user = await user_repo.create("seller", "password123", "s@ex.com", True)
        ad_repo = AdvertisementRepository()
        ad = await ad_repo.create(user.id, "Ad", "Desc", 1, 1)

        repo = ModerationRepository()
        pending = await repo.create_pending(ad.id)
        assert pending.id is not None
        assert pending.status == "pending"

        fetched = await repo.get_result_by_id(pending.id)
        assert fetched is not None
        assert fetched.item_id == ad.id

    @pytest.mark.parametrize("task_id,status,is_violation,prob,error", [
        (1, "completed", True, 0.85, None),
        (2, "failed", None, None, "error"),
    ])
    async def test_update_result(self, task_id, status, is_violation, prob, error):
        user_repo = UserRepository()
        user = await user_repo.create("seller", "password123", "s@ex.com", True)
        ad_repo = AdvertisementRepository()
        ad = await ad_repo.create(user.id, "Ad", "Desc", 1, 1)

        repo = ModerationRepository()
        pending = await repo.create_pending(ad.id)
        await repo.update_result(pending.id, status, is_violation, prob, error)
        updated = await repo.get_result_by_id(pending.id)
        assert updated.status == status
        assert updated.is_violation == is_violation
        assert updated.probability == prob
        assert updated.error_message == error


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.usefixtures("clean_db")
class TestUserRepositoryIntegration:
    @pytest.mark.parametrize("login,password,email,verified", [
        ("user1", "pass1234", "u1@ex.com", False),
        ("user2", "pass5678", "u2@ex.com", True),
    ])
    async def test_create_and_get(self, login, password, email, verified):
        repo = UserRepository()
        created = await repo.create(login, password, email, verified)
        assert created.id is not None

        fetched = await repo.get_by_id(created.id)
        assert fetched.login == login
        assert fetched.email == email
        assert fetched.is_verified_seller == verified

    @pytest.mark.parametrize("user_id", [999])
    async def test_get_not_found(self, user_id):
        repo = UserRepository()
        fetched = await repo.get_by_id(user_id)
        assert fetched is None


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.usefixtures("clean_db")
class TestAccountRepositoryIntegration:
    @pytest.mark.parametrize("login,password", [
        ("acc1", "12345678"),
        ("acc2", "abcdefgh"),
    ])
    async def test_create_and_get(self, login, password):
        repo = AccountRepository()
        created = await repo.create(login, password)
        assert created.id is not None

        fetched = await repo.get_by_id(created.id)
        assert fetched.login == login
        assert fetched.is_blocked is False

    @pytest.mark.parametrize("account_id", [999])
    async def test_get_by_id_not_found(self, account_id):
        repo = AccountRepository()
        with pytest.raises(UserNotFoundError):
            await repo.get_by_id(account_id)

    @pytest.mark.parametrize("account_id", [1])
    async def test_block(self, account_id):
        repo = AccountRepository()
        created = await repo.create("blockme", "12345678")
        blocked = await repo.block(created.id)
        assert blocked.is_blocked is True
        fetched = await repo.get_by_id(created.id)
        assert fetched.is_blocked is True
