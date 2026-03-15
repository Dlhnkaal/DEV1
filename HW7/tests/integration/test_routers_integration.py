import pytest
import pytest_asyncio
from httpx import AsyncClient
from fastapi import status
from unittest.mock import AsyncMock

from main import app
from dependencies import get_current_account
from models.advertisement import PredictionResult

pytestmark = pytest.mark.integration

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
        images_qty=2,
    )


@pytest_asyncio.fixture
async def auth_client(async_client: AsyncClient, sample_account):
    app.dependency_overrides[get_current_account] = lambda: sample_account
    yield async_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio(loop_scope="session")
class TestPredictEndpointIntegration:

    @pytest.mark.parametrize("is_violation,probability", [
        (True,  0.9), 
        (False, 0.1),  
    ])
    async def test_predict_positive_and_negative(
            self, auth_client: AsyncClient, sample_user,
            is_violation: bool, probability: float):
        
        app.state.ml_service.predict.return_value = PredictionResult(
            is_violation=is_violation, probability=probability
        )
        payload = {
            "seller_id": sample_user.id,
            "name": "Test Item",
            "description": "Normal description text",
            "category": 1,
            "images_qty": 5,
            "item_id": 10,
            "is_verified_seller": True,
        }
        response = await auth_client.post("/advertisement/predict", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_violation"] == is_violation
        assert abs(data["probability"] - probability) < 1e-6

    async def test_predict_requires_auth(self, async_client: AsyncClient):
        response = await async_client.post(
            "/advertisement/predict",
            json={"seller_id": 1, "name": "T", "description": "d",
                  "category": 1, "images_qty": 1, "item_id": 1,
                  "is_verified_seller": True},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.parametrize("bad_payload", [
        {"seller_id": 0,  "name": "T", "description": "d",
         "category": 1, "images_qty": 1,  "item_id": 1, "is_verified_seller": True},
        {"seller_id": 1,  "name": "T", "description": "d",
         "category": 1, "images_qty": 11, "item_id": 1, "is_verified_seller": True},
        {"seller_id": 1,  "name": "T", "description": "d",
         "category": 1, "images_qty": 1,  "item_id": 0, "is_verified_seller": True},
        {"seller_id": 1,  "name": "",  "description": "d",
         "category": 1, "images_qty": 1,  "item_id": 1, "is_verified_seller": True},
    ])
    async def test_predict_invalid_input_returns_422(
            self, auth_client: AsyncClient, bad_payload):
        response = await auth_client.post("/advertisement/predict", json=bad_payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_predict_model_unavailable_returns_503(
            self, auth_client: AsyncClient, sample_user):
        from errors import ModelNotReadyError
        app.state.ml_service.predict.side_effect = ModelNotReadyError("no model")
        payload = {
            "seller_id": sample_user.id,
            "name": "Test",
            "description": "desc",
            "category": 1,
            "images_qty": 1,
            "item_id": 10,
            "is_verified_seller": True,
        }
        response = await auth_client.post("/advertisement/predict", json=payload)
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        app.state.ml_service.predict.side_effect = None
        app.state.ml_service.predict.return_value = PredictionResult(
            is_violation=False, probability=0.1
        )


@pytest.mark.asyncio(loop_scope="session")
class TestSimplePredictEndpointIntegration:

    @pytest.mark.parametrize("is_violation,probability", [
        (True,  0.85),
        (False, 0.15),
    ])
    async def test_simple_predict_positive_and_negative(
            self, auth_client: AsyncClient, sample_advertisement,
            is_violation: bool, probability: float):
        
        app.state.ml_service.simple_predict.return_value = PredictionResult(
            is_violation=is_violation, probability=probability
        )
        response = await auth_client.post(
            "/advertisement/simple_predict",
            json={"item_id": sample_advertisement.id},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_violation"] == is_violation
        assert abs(data["probability"] - probability) < 1e-6

    async def test_simple_predict_ad_not_found_returns_404(
            self, auth_client: AsyncClient, clean_db):
        from errors import AdvertisementNotFoundError
        app.state.ml_service.simple_predict.side_effect = AdvertisementNotFoundError(
            "Advertisement 9999 not found"
        )
        response = await auth_client.post(
            "/advertisement/simple_predict", json={"item_id": 9999}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        app.state.ml_service.simple_predict.side_effect = None

    async def test_simple_predict_requires_auth(self, async_client: AsyncClient):
        response = await async_client.post(
            "/advertisement/simple_predict", json={"item_id": 1}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.parametrize("bad_payload", [
        {"item_id": 0},
        {"item_id": -1},
        {},
    ])
    async def test_simple_predict_invalid_input_returns_422(
            self, auth_client: AsyncClient, bad_payload):
        response = await auth_client.post(
            "/advertisement/simple_predict", json=bad_payload
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_simple_predict_model_unavailable_returns_503(
            self, auth_client: AsyncClient, sample_advertisement):
        from errors import ModelNotReadyError
        app.state.ml_service.simple_predict.side_effect = ModelNotReadyError()
        response = await auth_client.post(
            "/advertisement/simple_predict",
            json={"item_id": sample_advertisement.id},
        )
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        app.state.ml_service.simple_predict.side_effect = None
        app.state.ml_service.simple_predict.return_value = PredictionResult(
            is_violation=False, probability=0.1
        )


@pytest.mark.asyncio(loop_scope="session")
class TestModerationRouterIntegration:

    async def test_async_predict_accepted(
            self, auth_client: AsyncClient, sample_advertisement):
        response = await auth_client.post(
            "/moderation/async_predict",
            json={"item_id": sample_advertisement.id},
        )
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"

    async def test_async_predict_ad_not_found(
            self, auth_client: AsyncClient, clean_db):
        response = await auth_client.post(
            "/moderation/async_predict", json={"item_id": 99999}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_moderation_result_pending(
            self, auth_client: AsyncClient, sample_advertisement):
        from repositories.moderation import ModerationRepository
        repo = ModerationRepository()
        pending = await repo.create_pending(sample_advertisement.id)

        response = await auth_client.get(
            f"/moderation/moderation_result/{pending.id}"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["task_id"] == pending.id
        assert data["status"] == "pending"

    async def test_get_moderation_result_not_found(
            self, auth_client: AsyncClient, clean_db):
        response = await auth_client.get("/moderation/moderation_result/999")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio(loop_scope="session")
class TestAuthRouterIntegration:

    async def test_login_success(
            self, async_client: AsyncClient, sample_account):
        response = await async_client.post(
            "/auth/login",
            json={"login": "testlogin", "password": "testpassword"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert "x-user-token" in response.cookies
        assert "x-refresh-token" in response.cookies

    async def test_login_wrong_password(
            self, async_client: AsyncClient, sample_account):
        response = await async_client.post(
            "/auth/login",
            json={"login": "testlogin", "password": "wrongpassword"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["message"] == "Login or password is not corrected"

    async def test_login_unknown_user(
            self, async_client: AsyncClient, clean_db):
        response = await async_client.post(
            "/auth/login",
            json={"login": "nobody", "password": "wrongpass"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_login_sets_httponly_cookies(
            self, async_client: AsyncClient, sample_account):
        response = await async_client.post(
            "/auth/login",
            json={"login": "testlogin", "password": "testpassword"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert "x-user-token" in response.cookies
        assert "x-refresh-token" in response.cookies


@pytest.mark.asyncio(loop_scope="session")
class TestErrorHandlersIntegration:

    async def test_unauthorized_no_cookie_returns_401(
            self, async_client: AsyncClient):
        response = await async_client.post(
            "/advertisement/simple_predict", json={"item_id": 1}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["message"] == "User not authorized"

    async def test_authorized_error_wrong_credentials_returns_400(
            self, async_client: AsyncClient, clean_db):
        response = await async_client.post(
            "/auth/login", json={"login": "nobody", "password": "wrongpass"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["message"] == "Login or password is not corrected"