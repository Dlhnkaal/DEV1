import pytest
from datetime import datetime
from unittest.mock import AsyncMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from models.user import UserInDB
from repositories.user import UserRepository, UserRedisStorage


@pytest.mark.asyncio
class TestUserRepository:

    @pytest.mark.parametrize("login,password,email,is_verified_seller,expected_id", [
        ("alice", "pass1234", "a@ex.com", False, 1),
        ("bob", "securepwd", "b@ex.com", True, 2)])
    async def test_create(self, mock_user_storage, login, password, email, is_verified_seller, expected_id):
        now = datetime.now()
        mock_user_storage.create.return_value = {
            "id": expected_id,
            "login": login,
            "password": "hashed123",
            "email": email,
            "is_verified_seller": is_verified_seller,
            "created_at": now,
            "updated_at": now
        }

        repo = UserRepository(storage=mock_user_storage)
        result = await repo.create(login, password, email, is_verified_seller)

        assert isinstance(result, UserInDB)
        assert result.id == expected_id
        assert result.login == login
        assert result.password == "hashed123"
        assert result.email == email
        assert result.is_verified_seller == is_verified_seller
        assert result.created_at == now
        assert result.updated_at == now

        mock_user_storage.create.assert_called_once_with(
            login=login,
            password=password,
            email=email,
            is_verified_seller=is_verified_seller
        )

    async def test_get_by_id_cache_miss(self, mock_user_storage):
        user_id = 1
        now = datetime.now()
        user_data = {
            "id": user_id,
            "login": "testuser",
            "password": "hashed123",
            "email": "test@ex.com",
            "is_verified_seller": False,
            "created_at": now,
            "updated_at": now
        }

        mock_redis = AsyncMock(spec=UserRedisStorage)
        mock_redis.get.return_value = None
        mock_user_storage.get_by_id.return_value = user_data

        repo = UserRepository(storage=mock_user_storage, redis_storage=mock_redis)
        result = await repo.get_by_id(user_id)

        assert isinstance(result, UserInDB)
        assert result.id == user_id
        assert result.login == "testuser"
        assert result.email == "test@ex.com"

        mock_user_storage.get_by_id.assert_called_once_with(user_id)
        mock_redis.set.assert_called_once_with(user_id, user_data)

    async def test_get_by_id_cache_hit(self, mock_user_storage):
        user_id = 2
        now = datetime.now()
        user_data = {
            "id": user_id,
            "login": "cached_user",
            "password": "hashed123",
            "email": "cached@ex.com",
            "is_verified_seller": True,
            "created_at": now,
            "updated_at": now
        }

        mock_redis = AsyncMock(spec=UserRedisStorage)
        mock_redis.get.return_value = user_data

        repo = UserRepository(storage=mock_user_storage, redis_storage=mock_redis)
        result = await repo.get_by_id(user_id)

        assert isinstance(result, UserInDB)
        assert result.id == user_id
        assert result.login == "cached_user"
        assert result.email == "cached@ex.com"

        mock_user_storage.get_by_id.assert_not_called()
        mock_redis.get.assert_called_once_with(user_id)
        mock_redis.set.assert_not_called()

    async def test_get_by_id_not_found(self, mock_user_storage):
        user_id = 999
        mock_redis = AsyncMock(spec=UserRedisStorage)
        mock_redis.get.return_value = None
        mock_user_storage.get_by_id.return_value = None

        repo = UserRepository(storage=mock_user_storage, redis_storage=mock_redis)
        result = await repo.get_by_id(user_id)

        assert result is None
        mock_user_storage.get_by_id.assert_called_once_with(user_id)
        mock_redis.set.assert_not_called()

    @pytest.mark.parametrize("mock_return,expected_count", [
        ([], 0),
        ([{
            "id": 1,
            "login": "testuser",
            "password": "hashed_password",
            "email": "test@example.com",
            "is_verified_seller": False,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }], 1),
        ([
            {
                "id": 1,
                "login": "user1",
                "password": "hash1388383",
                "email": "user1@ex.com",
                "is_verified_seller": False,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            },
            {
                "id": 2,
                "login": "user2",
                "password": "hash233838",
                "email": "user2@ex.com",
                "is_verified_seller": True,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
        ], 2)
    ])
    async def test_get_all(self, mock_user_storage, mock_return, expected_count):
        mock_user_storage.get_all.return_value = mock_return
        repo = UserRepository(storage=mock_user_storage)

        result = await repo.get_all()

        assert len(result) == expected_count
        if expected_count > 0:
            assert all(isinstance(user, UserInDB) for user in result)
            for i, user in enumerate(result):
                assert user.id == mock_return[i]["id"]
                assert user.login == mock_return[i]["login"]
                assert user.email == mock_return[i]["email"]

        mock_user_storage.get_all.assert_called_once()