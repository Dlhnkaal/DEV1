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

    async def test_create_and_get(self):
        user_repo = UserRepository()
        user = await user_repo.create("seller_cag", "password123", "cag@ex.com", True)
        repo = AdvertisementRepository()
        created = await repo.create(user.id, "Ad1", "Desc", 1, 1)
        assert created.id is not None
        fetched = await repo.get_by_id_with_user(created.id)
        assert fetched is not None
        assert fetched.name == "Ad1"

    @pytest.mark.parametrize("item_id", [9999])
    async def test_get_not_found(self, item_id):
        repo = AdvertisementRepository()
        fetched = await repo.get_by_id_with_user(item_id)
        assert fetched is None

    async def test_close_existing(self):
        user_repo = UserRepository()
        user = await user_repo.create("seller_close", "password123", "close@ex.com", True)
        ad_repo = AdvertisementRepository()
        ad = await ad_repo.create(user.id, "Ad", "Desc", 1, 1)
        result = await ad_repo.close(ad.id)
        assert result.success is True

    async def test_close_not_found(self):
        ad_repo = AdvertisementRepository()
        result = await ad_repo.close(999999)
        assert result.success is False


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.usefixtures("clean_db")
class TestModerationRepositoryIntegration:

    async def test_create_pending_and_get(self):
        user_repo = UserRepository()
        user = await user_repo.create("seller_mod", "password123", "mod@ex.com", True)
        ad_repo = AdvertisementRepository()
        ad = await ad_repo.create(user.id, "Ad", "Desc", 1, 1)

        repo = ModerationRepository()
        pending = await repo.create_pending(ad.id)
        assert pending.id is not None
        assert pending.status == "pending"

        fetched = await repo.get_result_by_id(pending.id)
        assert fetched is not None
        assert fetched.item_id == ad.id

    @pytest.mark.parametrize("status,is_violation,prob,error", [
        ("completed", True, 0.85, None),
        ("failed", None, None, "error"),
    ])
    async def test_update_result(self, status, is_violation, prob, error):
        user_repo = UserRepository()
        user = await user_repo.create(
            f"seller_upd_{status}", "password123", f"upd_{status}@ex.com", True
        )
        ad_repo = AdvertisementRepository()
        ad = await ad_repo.create(user.id, "Ad", "Desc", 1, 1)

        repo = ModerationRepository()
        pending = await repo.create_pending(ad.id)
        await repo.update_result(pending.id, status, is_violation, prob, error)
        await repo.delete_cache(pending.id)
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
    async def test_create_and_get_by_id(self, login, password):
        repo = AccountRepository()
        created = await repo.create(login, password)
        assert created.id is not None
        assert created.login == login
        assert created.is_blocked is False

        fetched = await repo.get_by_id(created.id)
        assert fetched.login == login
        assert fetched.is_blocked is False

    async def test_get_by_id_not_found_raises(self):
        repo = AccountRepository()
        with pytest.raises(UserNotFoundError):
            await repo.get_by_id(99999)

    async def test_delete_removes_account(self):
        repo = AccountRepository()
        created = await repo.create("to_delete", "12345678")
        deleted = await repo.delete(created.id)
        assert deleted.id == created.id

        with pytest.raises(UserNotFoundError):
            await repo.get_by_id(created.id)

    async def test_delete_not_found_raises(self):
        repo = AccountRepository()
        with pytest.raises(UserNotFoundError):
            await repo.delete(99999)

    async def test_block_sets_flag(self):
        repo = AccountRepository()
        created = await repo.create("to_block", "12345678")
        blocked = await repo.block(created.id)
        assert blocked.is_blocked is True

        fetched = await repo.get_by_id(created.id)
        assert fetched.is_blocked is True

    async def test_block_not_found_raises(self):
        repo = AccountRepository()
        with pytest.raises(UserNotFoundError):
            await repo.block(99999)

    @pytest.mark.parametrize("login,password", [
        ("login_user", "correctpass"),
    ])
    async def test_get_by_login_and_password_success(self, login, password):
        repo = AccountRepository()
        await repo.create(login, password)

        result = await repo.get_by_login_and_password(login, password)
        assert isinstance(result, AccountModel)
        assert result.login == login

    @pytest.mark.parametrize("login,password,wrong_password", [
        ("pw_user", "correctpass", "wrongpass"),
    ])
    async def test_get_by_login_and_password_wrong_password_raises(
            self, login, password, wrong_password):
        repo = AccountRepository()
        await repo.create(login, password)

        with pytest.raises(UserNotFoundError):
            await repo.get_by_login_and_password(login, wrong_password)

    async def test_get_by_login_and_password_unknown_user_raises(self):
        repo = AccountRepository()
        with pytest.raises(UserNotFoundError):
            await repo.get_by_login_and_password("ghost", "anypass")