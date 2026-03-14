import pytest
from unittest.mock import AsyncMock, patch
from datetime import timedelta
from repositories.advertisement import AdvertisementRepository
from repositories.moderation import ModerationRepository
from repositories.auth import AuthRepository
from repositories.user import UserRepository
from repositories.account import AccountRepository
from errors import UserNotFoundError
from models.account import AccountModel
from models.user import UserInDB # Добавлен импорт
from models.advertisement import AdvertisementWithUserBase, AdvertisementInDB # Добавлен импорт

class TestAdvertisementRepository:
    @pytest.mark.parametrize("item_id,cached,storage_return", [
        (1, {"item_id": 1, "seller_id": 1, "name": "Ad", "description": "Desc", "category": 1, "images_qty": 1, "is_verified_seller": True}, {"item_id": 1, "seller_id": 1, "name": "Ad", "description": "Desc", "category": 1, "images_qty": 1, "is_verified_seller": True}),
        (2, None, {"item_id": 2, "seller_id": 1, "name": "Ad", "description": "Desc", "category": 1, "images_qty": 1, "is_verified_seller": True}),
        (3, None, None),
    ])
    async def test_get_by_id_with_user(self, item_id, cached, storage_return):
        repo = AdvertisementRepository()
        with patch.object(repo.redis_storage, 'get', AsyncMock(return_value=cached)) as mock_redis_get, \
             patch.object(repo.storage, 'get_by_id_with_user', AsyncMock(return_value=storage_return)) as mock_storage_get, \
             patch.object(repo.redis_storage, 'set', AsyncMock()) as mock_redis_set:
            result = await repo.get_by_id_with_user(item_id)
            
            if cached or storage_return:
                assert result.item_id == item_id
                assert isinstance(result, AdvertisementWithUserBase)
            else:
                assert result is None
                
            mock_redis_get.assert_awaited_once_with(item_id)
            if not cached:
                mock_storage_get.assert_awaited_once_with(item_id)
                if storage_return:
                    mock_redis_set.assert_awaited_once_with(item_id, storage_return)

    @pytest.mark.parametrize("item_id,storage_result", [
        (1, {"id": 1}),
        (2, {}),
    ])
    async def test_close(self, item_id, storage_result):
        repo = AdvertisementRepository()
        with patch.object(repo.storage, 'delete', AsyncMock(return_value=storage_result)) as mock_storage_delete, \
             patch.object(repo.redis_storage, 'delete', AsyncMock()) as mock_redis_delete:
            result = await repo.close(item_id)
            mock_storage_delete.assert_awaited_once_with(item_id)
            if storage_result:
                assert result is True
                mock_redis_delete.assert_awaited_once_with(item_id)
            else:
                assert result is False

class TestModerationRepository:
    @pytest.mark.parametrize("task_id,cached,storage_return", [
        (1, {"id": 1}, {"id": 1}),
        (2, None, {"id": 2}),
        (3, None, None),
    ])
    async def test_get_result_by_id(self, task_id, cached, storage_return):
        repo = ModerationRepository()
        with patch.object(repo.redis_storage, 'get', AsyncMock(return_value=cached)) as mock_redis_get, \
             patch.object(repo.storage, 'get_by_id', AsyncMock(return_value=storage_return)) as mock_storage_get, \
             patch.object(repo.redis_storage, 'set', AsyncMock()) as mock_redis_set:
            result = await repo.get_result_by_id(task_id)
            if cached or storage_return:
                assert result.id == task_id
            else:
                assert result is None
            mock_redis_get.assert_awaited_once_with(task_id)
            if not cached:
                mock_storage_get.assert_awaited_once_with(task_id)
                if storage_return:
                    mock_redis_set.assert_awaited_once_with(task_id, storage_return)

    @pytest.mark.parametrize("task_id,status,is_violation,probability,error_message", [
        (1, "completed", True, 0.9, None),
        (2, "failed", None, None, "error"),
    ])
    async def test_update_result(self, task_id, status, is_violation, probability, error_message):
        repo = ModerationRepository()
        with patch.object(repo.storage, 'update_result', AsyncMock()) as mock_storage_update, \
             patch.object(repo.redis_storage, 'delete', AsyncMock()) as mock_redis_delete:
            await repo.update_result(task_id, status, is_violation, probability, error_message)
            mock_storage_update.assert_awaited_once_with(
                task_id=task_id,
                status=status,
                is_violation=is_violation,
                probability=probability,
                error_message=error_message
            )
            mock_redis_delete.assert_awaited_once_with(task_id)

class TestAuthRepository:
    @pytest.mark.parametrize("refresh_token,stored_id", [
        ("token123", 42),
        ("invalid", None),
    ])
    async def test_get_user_id_by_refresh_token(self, refresh_token, stored_id):
        repo = AuthRepository()
        with patch.object(repo.redis_storage, 'get', AsyncMock(return_value=str(stored_id) if stored_id else None)) as mock_get:
            result = await repo.get_user_id_by_refresh_token(refresh_token)
            assert result == stored_id
            mock_get.assert_awaited_once_with(refresh_token)

    @pytest.mark.parametrize("user_id,new_token,ttl,old_token", [
        (1, "new", timedelta(days=1), "old"),
        (2, "new2", timedelta(hours=12), None),
    ])
    async def test_update_refresh_token(self, user_id, new_token, ttl, old_token):
        repo = AuthRepository()
        with patch.object(repo.redis_storage, 'delete', AsyncMock()) as mock_delete, \
             patch.object(repo.redis_storage, 'set', AsyncMock()) as mock_set:
            result = await repo.update_refresh_token(user_id, new_token, ttl, old_token)
            assert result is True
            if old_token:
                mock_delete.assert_awaited_once_with(old_token)
            mock_set.assert_awaited_once_with(user_id=user_id, refresh_token=new_token, ttl=ttl)

class TestAccountRepository:
    @pytest.mark.parametrize("account_id,storage_return,should_raise", [
        (1, {"id": 1, "login": "test", "password": "hashed1234", "is_blocked": False}, False),
        (2, None, True),
    ])
    async def test_get_by_id(self, account_id, storage_return, should_raise):
        repo = AccountRepository()
        with patch.object(repo.storage, 'get_by_id', AsyncMock(return_value=storage_return)) as mock_get:
            if should_raise:
                with pytest.raises(UserNotFoundError):
                    await repo.get_by_id(account_id)
            else:
                result = await repo.get_by_id(account_id)
                assert result.id == account_id
                assert isinstance(result, AccountModel)
            mock_get.assert_awaited_once_with(account_id)
