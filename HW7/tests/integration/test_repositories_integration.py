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

pytestmark = pytest.mark.integration

@pytest_asyncio.fixture(scope="function")
async def clean_db():
    from clients.postgres import get_pg_connection
    async with get_pg_connection() as conn:
        await conn.execute("TRUNCATE users, advertisements, moderation_results, account RESTART IDENTITY CASCADE")
    yield

@pytest_asyncio.fixture
async def sample_user(clean_db):
    repo = UserRepository()
    user = await repo.create(
        login="testuser",
        password="password",
        email="test@example.com",
        is_verified_seller=True
    )
    return user

@pytest_asyncio.fixture
async def sample_advertisement(sample_user):
    repo = AdvertisementRepository()
    ad = await repo.create(
        seller_id=sample_user.id,
        name="Test Ad",
        description="Description",
        category=5,
        images_qty=3
    )
    return ad

@pytest.mark.asyncio
class TestAdvertisementRepositoryIntegration:
    @pytest.mark.parametrize("seller_id,name,desc,category,img_qty", [
        (1, "Ad1", "Desc", 1, 1),
    ])
    async def test_create_and_get(self, seller_id, name, desc, category, img_qty, sample_user):
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
    async def test_close(self, item_id, expected, sample_advertisement):
        repo = AdvertisementRepository()
        result = await repo.close(item_id if item_id == 1 else 999)
        assert result == (item_id == 1)

@pytest.mark.asyncio
class TestModerationRepositoryIntegration:
    @pytest.mark.parametrize("item_id", [1])
    async def test_create_pending_and_get(self, item_id, sample_advertisement):
        repo = ModerationRepository()
        pending = await repo.create_pending(item_id)
        assert pending.id is not None
        assert pending.status == "pending"

        fetched = await repo.get_result_by_id(pending.id)
        assert fetched is not None
        assert fetched.item_id == item_id

    @pytest.mark.parametrize("task_id,status,is_violation,prob,error", [
        (1, "completed", True, 0.85, None),
        (2, "failed", None, None, "error"),
    ])
    async def test_update_result(self, task_id, status, is_violation, prob, error, sample_advertisement):
        repo = ModerationRepository()
        pending = await repo.create_pending(sample_advertisement.id)
        await repo.update_result(pending.id, status, is_violation, prob, error)
        updated = await repo.get_result_by_id(pending.id)
        assert updated.status == status
        assert updated.is_violation == is_violation
        assert updated.probability == prob
        assert updated.error_message == error

@pytest.mark.asyncio
class TestUserRepositoryIntegration:
    @pytest.mark.parametrize("login,password,email,verified", [
        ("user1", "pass", "u1@ex.com", False),
        ("user2", "pass2", "u2@ex.com", True),
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

@pytest.mark.asyncio
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
        from errors import UserNotFoundError
        with pytest.raises(UserNotFoundError):
            await repo.get_by_id(account_id)

    @pytest.mark.parametrize("account_id", [1])
    async def test_block(self, account_id, sample_account):
        repo = AccountRepository()
        blocked = await repo.block(account_id)
        assert blocked.is_blocked is True
        fetched = await repo.get_by_id(account_id)
        assert fetched.is_blocked is True