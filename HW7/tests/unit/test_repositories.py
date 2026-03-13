import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from repositories.advertisement import AdvertisementRepository
from repositories.moderation import ModerationRepository
from repositories.user import UserRepository
from repositories.auth import AuthRepository
from repositories.account import AccountRepository
from models.advertisement import AdvertisementWithUserBase
from models.moderation import ModerationResultInDB

class TestAdvertisementRepository:
    @pytest.mark.parametrize("item_id,cached_data,expected_result", [
        (1, {"item_id": 1, "seller_id": 1, "name": "test"}, AdvertisementWithUserBase(item_id=1, seller_id=1, name="test", description="", category=0, images_qty=0, is_verified_seller=False)),
        (2, None, None),
    ])
    async def test_get_by_id_with_user_cache_hit(self, item_id, cached_data, expected_result):
        repo = AdvertisementRepository()
        repo.redis_storage.get = AsyncMock(return_value=cached_data)
        repo.storage.get_by_id_with_user = AsyncMock(return_value=None)
        result = await repo.get_by_id_with_user(item_id)
        if expected_result:
            assert result == expected_result
        else:
            assert result is None
        repo.redis_storage.get.assert_awaited_once_with(item_id)
        if not cached_data:
            repo.storage.get_by_id_with_user.assert_awaited_once_with(item_id)

    @pytest.mark.parametrize("item_id,storage_return,expected", [
        (1, {"item_id": 1, "seller_id": 1}, True),
        (2, None, False),
    ])
    async def test_close_advertisement(self, item_id, storage_return, expected):
        repo = AdvertisementRepository()
        repo.storage.delete = AsyncMock(return_value=storage_return)
        repo.redis_storage.delete = AsyncMock()
        result = await repo.close(item_id)
        assert result == expected
        repo.storage.delete.assert_awaited_once_with(item_id)
        if storage_return:
            repo.redis_storage.delete.assert_awaited_once_with(item_id)

class TestModerationRepository:
    @pytest.mark.parametrize("task_id,cached,storage_return", [
        (1, {"id": 1}, {"id": 1}),
        (2, None, {"id": 2}),
        (3, None, None),
    ])
    async def test_get_result_by_id(self, task_id, cached, storage_return):
        repo = ModerationRepository()
        repo.redis_storage.get = AsyncMock(return_value=cached)
        repo.storage.get_by_id = AsyncMock(return_value=storage_return)
        repo.redis_storage.set = AsyncMock()
        result = await repo.get_result_by_id(task_id)
        if cached or storage_return:
            assert result.id == task_id
        else:
            assert result is None
        repo.redis_storage.get.assert_awaited_once_with(task_id)
        if not cached:
            repo.storage.get_by_id.assert_awaited_once_with(task_id)
            if storage_return:
                repo.redis_storage.set.assert_awaited_once_with(task_id, storage_return)

    @pytest.mark.parametrize("task_id,status,is_violation,probability,error_message", [
        (1, "completed", True, 0.9, None),
        (2, "failed", None, None, "error"),
    ])
    async def test_update_result(self, task_id, status, is_violation, probability, error_message):
        repo = ModerationRepository()
        repo.storage.update_result = AsyncMock()
        repo.redis_storage.delete = AsyncMock()
        await repo.update_result(task_id, status, is_violation, probability, error_message)
        repo.storage.update_result.assert_awaited_once_with(
            task_id=task_id,
            status=status,
            is_violation=is_violation,
            probability=probability,
            error_message=error_message
        )
        repo.redis_storage.delete.assert_awaited_once_with(task_id)

class TestAuthRepository:
    @pytest.mark.parametrize("refresh_token,stored_id", [
        ("token123", 42),
        ("invalid", None),
    ])
    async def test_get_user_id_by_refresh_token(self, refresh_token, stored_id):
        repo = AuthRepository()
        repo.redis_storage.get = AsyncMock(return_value=str(stored_id) if stored_id else None)
        result = await repo.get_user_id_by_refresh_token(refresh_token)
        assert result == stored_id
        repo.redis_storage.get.assert_awaited_once_with(refresh_token)

    @pytest.mark.parametrize("user_id,new_token,ttl,old_token", [
        (1, "new", timedelta(days=1), "old"),
        (2, "new2", timedelta(hours=12), None),
    ])
    async def test_update_refresh_token(self, user_id, new_token, ttl, old_token):
        repo = AuthRepository()
        repo.redis_storage.delete = AsyncMock()
        repo.redis_storage.set = AsyncMock()
        result = await repo.update_refresh_token(user_id, new_token, ttl, old_token)
        assert result is True
        if old_token:
            repo.redis_storage.delete.assert_awaited_once_with(old_token)
        repo.redis_storage.set.assert_awaited_once_with(user_id=user_id, refresh_token=new_token, ttl=ttl)

class TestUserRepository:
    @pytest.mark.parametrize("user_id,cached,storage_return", [
        (1, {"id": 1}, {"id": 1}),
        (2, None, {"id": 2}),
        (3, None, None),
    ])
    async def test_get_by_id(self, user_id, cached, storage_return):
        from models.user import UserInDB
        repo = UserRepository()
        repo.redis_storage.get = AsyncMock(return_value=cached)
        repo.storage.get_by_id = AsyncMock(return_value=storage_return)
        repo.redis_storage.set = AsyncMock()
        result = await repo.get_by_id(user_id)
        if cached or storage_return:
            assert result.id == user_id
        else:
            assert result is None
        if not cached:
            if storage_return:
                repo.redis_storage.set.assert_awaited_once_with(user_id, storage_return)

class TestAccountRepository:
    @pytest.mark.parametrize("account_id,storage_return,should_raise", [
        (1, {"id": 1}, False),
        (2, None, True),
    ])
    async def test_get_by_id(self, account_id, storage_return, should_raise):
        from repositories.account import AccountRepository
        from errors import UserNotFoundError
        repo = AccountRepository()
        repo.storage.get_by_id = AsyncMock(return_value=storage_return)
        if should_raise:
            with pytest.raises(UserNotFoundError):
                await repo.get_by_id(account_id)
        else:
            result = await repo.get_by_id(account_id)
            assert result.id == account_id