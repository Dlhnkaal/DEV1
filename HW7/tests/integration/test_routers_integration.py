import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from fastapi import status
from unittest.mock import AsyncMock


from main import app
from dependencies import get_current_account
from models.account import AccountModel


pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def auth_client(async_client: AsyncClient, sample_account):
    """Клиент с авторизованным пользователем."""
    app.dependency_overrides[get_current_account] = lambda: sample_account
    yield async_client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_account(clean_db):
    from repositories.account import AccountRepository
    repo = AccountRepository()
    return await repo.create("testlogin", "testpassword")


@pytest_asyncio.fixture
async def sample_user(clean_db):
    from repositories.user import UserRepository
    repo = UserRepository()
    return await repo.create("seller", "pass1234", "s@ex.com", True)


@pytest_asyncio.fixture
async def sample_advertisement(sample_user):
    from repositories.advertisement import AdvertisementRepository
    repo = AdvertisementRepository()
    return await repo.create(
        seller_id=sample_user.id,
        name="Ad",
        description="Desc",
        category=1,
        images_qty=2
    )


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.usefixtures("clean_db")
class TestAdvertisementRouterIntegration:
    @pytest.mark.parametrize("payload", [{"item_id": 1}])
    async def test_simple_predict(self, auth_client: AsyncClient, payload, sample_advertisement):
        response = await auth_client.post("/advertisement/simple_predict", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "is_violation" in data
        assert "probability" in data


    @pytest.mark.parametrize("payload", [{"item_id": 9999}])
    async def test_simple_predict_not_found(self, auth_client: AsyncClient, payload):
        response = await auth_client.post("/advertisement/simple_predict", json=payload)
        assert response.status_code == status.HTTP_404_NOT_FOUND


    @pytest.mark.parametrize("payload,expected_status", [
        ({"seller_id": 1, "name": "Test", "description": "desc", "category": 1, "images_qty": 5, "item_id": 10, "is_verified_seller": True}, 200),
    ])
    async def test_predict(self, auth_client: AsyncClient, payload, expected_status, sample_user):
        response = await auth_client.post("/advertisement/predict", json=payload)
        assert response.status_code == expected_status


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.usefixtures("clean_db")
class TestModerationRouterIntegration:
    @pytest.mark.parametrize("payload", [{"item_id": 1}])
    async def test_async_predict(self, auth_client: AsyncClient, payload, sample_advertisement, monkeypatch):
        # мокаем Kafka, чтобы не отправлять реально
        from services.moderation import AsyncModerationService
        mock_producer = AsyncMock()
        monkeypatch.setattr(AsyncModerationService, "producer", mock_producer)  
        response = await auth_client.post("/moderation/async_predict", json=payload)
        assert response.status_code == status.HTTP_202_ACCEPTED


    @pytest.mark.parametrize("task_id", [1])
    async def test_get_moderation_result(self, auth_client: AsyncClient, task_id, sample_advertisement):
        from repositories.moderation import ModerationRepository
        repo = ModerationRepository()
        pending = await repo.create_pending(sample_advertisement.id)
        response = await auth_client.get(f"/moderation/moderation_result/{pending.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["task_id"] == pending.id
        assert data["status"] == "pending"


    @pytest.mark.parametrize("task_id", [999])
    async def test_get_moderation_result_not_found(self, auth_client: AsyncClient, task_id):
        response = await auth_client.get(f"/moderation/moderation_result/{task_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.usefixtures("clean_db")
class TestAuthRouterIntegration:
    @pytest.mark.parametrize("login,password", [("testlogin", "testpassword")])
    async def test_login_success(self, async_client: AsyncClient, login, password, sample_account):
        response = await async_client.post("/auth/login", json={"login": login, "password": password})
        assert response.status_code == status.HTTP_200_OK
        cookies = response.cookies
        assert "x-user-token" in cookies
        assert "x-refresh-token" in cookies


    @pytest.mark.parametrize("login,password", [("wrong", "wrong")])
    async def test_login_failure(self, async_client: AsyncClient, login, password):
        response = await async_client.post("/auth/login", json={"login": login, "password": password})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
