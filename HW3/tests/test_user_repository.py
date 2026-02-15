import pytest
from unittest.mock import AsyncMock
from datetime import datetime
from models.user import UserCreate, UserInDB
from repositories.user import UserRepository, UserPostgresStorage
from errors import UserNotFoundError


@pytest.mark.asyncio
class TestUserRepository:
    @pytest.mark.parametrize("input_data,expected_id", [
        (UserCreate(login="alice", password="pass1234", email="a@ex.com", is_verified_seller=False), 1),
        (UserCreate(login="bob", password="securepwd", email="b@ex.com", is_verified_seller=True), 2)])
    async def test_create(self, mock_user_storage, input_data, expected_id):
        now = datetime.now()
        mock_user_storage.create.return_value = {
            "id": expected_id, "login": input_data.login, "password": "hashed123",
            "email": input_data.email, "is_verified_seller": input_data.is_verified_seller,
            "created_at": now, "updated_at": now}
        repo = UserRepository(storage=mock_user_storage)
        result = await repo.create(input_data)
        assert isinstance(result, UserInDB)
        assert result.id == expected_id
        assert result.login == input_data.login

    @pytest.mark.parametrize("user_id", [1, 5])
    async def test_get_by_id_success(self, mock_user_storage, user_id):
        now = datetime.now()
        mock_user_storage.get_by_id.return_value = {
            "id": user_id, "login": "user", "password": "hashed123", "email": "u@ex.com",
            "is_verified_seller": False, "created_at": now, "updated_at": now}
        repo = UserRepository(storage=mock_user_storage)
        result = await repo.get_by_id(user_id)
        assert isinstance(result, UserInDB)
        assert result.id == user_id

    @pytest.mark.parametrize("user_id", [999, -1])
    async def test_get_by_id_not_found(self, mock_user_storage, user_id):
        mock_user_storage.get_by_id.side_effect = UserNotFoundError("")
        repo = UserRepository(storage=mock_user_storage)
        with pytest.raises(UserNotFoundError):
            await repo.get_by_id(user_id)

    @pytest.mark.parametrize("mock_return,expected_count", 
        [([], 0), 
        ([{"id": 1, "login": "testuser", "password": "hashed_password", "email": "test@example.com", 
           "is_verified_seller": False, "created_at": datetime.now(), "updated_at": datetime.now()}], 1)])
    async def test_get_all(self, mock_user_storage, mock_return, expected_count):
        mock_user_storage.get_all.return_value = mock_return
        repo = UserRepository(storage=mock_user_storage)
        result = await repo.get_all()
        assert len(result) == expected_count
        if expected_count:
            assert isinstance(result[0], UserInDB)