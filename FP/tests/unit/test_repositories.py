import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta

from repositories.advertisement import AdvertisementRepository
from repositories.moderation import ModerationRepository
from repositories.auth import AuthRepository
from repositories.account import AccountRepository
from errors import UserNotFoundError
from models.account import AccountModel
from models.advertisement import AdvertisementWithUserBase, ActionStatus
from models.auth import UserIdResponse, TokenUpdateResponse


_AD_DATA = {
    "item_id": 1, "seller_id": 1, "name": "Ad",
    "description": "Desc", "category": 1,
    "images_qty": 1, "is_verified_seller": True,
}

_MOD_DATA = {
    "id": 1, "item_id": 10, "status": "pending",
    "is_violation": None, "probability": None,
    "error_message": None,
    "created_at": datetime(2024, 1, 1, 12, 0, 0),
    "processed_at": None,
}


class TestAdvertisementRepositoryCache:

    async def test_cache_hit_returns_result_without_db(self):
        repo = AdvertisementRepository()
        with patch.object(repo.redis_storage, 'get',
                          AsyncMock(return_value=_AD_DATA)) as mock_redis, \
             patch.object(repo.storage, 'get_by_id_with_user',
                          AsyncMock()) as mock_db:
            result = await repo.get_by_id_with_user(1)

        mock_db.assert_not_awaited()
        assert result is not None
        assert isinstance(result, AdvertisementWithUserBase)
        assert result.item_id == 1

    async def test_cache_miss_fetches_db_and_saves_to_cache(self):
        repo = AdvertisementRepository()
        with patch.object(repo.redis_storage, 'get',
                          AsyncMock(return_value=None)), \
             patch.object(repo.storage, 'get_by_id_with_user',
                          AsyncMock(return_value=_AD_DATA)) as mock_db, \
             patch.object(repo.redis_storage, 'set',
                          AsyncMock()) as mock_set:
            result = await repo.get_by_id_with_user(1)

        mock_db.assert_awaited_once_with(1)
        mock_set.assert_awaited_once_with(1, _AD_DATA)
        assert result.item_id == 1

    async def test_cache_not_populated_when_db_returns_none(self):
        repo = AdvertisementRepository()
        with patch.object(repo.redis_storage, 'get', AsyncMock(return_value=None)), \
             patch.object(repo.storage, 'get_by_id_with_user',
                          AsyncMock(return_value=None)), \
             patch.object(repo.redis_storage, 'set', AsyncMock()) as mock_set:
            result = await repo.get_by_id_with_user(999)

        assert result is None
        mock_set.assert_not_awaited()

    async def test_cache_invalidated_on_close(self):
        repo = AdvertisementRepository()
        with patch.object(repo.storage, 'close',
                          AsyncMock(return_value={"id": 1})), \
             patch.object(repo.redis_storage, 'delete',
                          AsyncMock()) as mock_del:
            result = await repo.close(1)

        mock_del.assert_awaited_once_with(1)
        assert isinstance(result, ActionStatus)
        assert result.success is True

    async def test_cache_not_invalidated_when_not_found(self):
        repo = AdvertisementRepository()
        with patch.object(repo.storage, 'close',
                          AsyncMock(return_value={})), \
             patch.object(repo.redis_storage, 'delete',
                          AsyncMock()) as mock_del:
            result = await repo.close(999)

        mock_del.assert_not_awaited()
        assert result.success is False


class TestModerationRepositoryCache:

    async def test_cache_hit_skips_db(self):
        repo = ModerationRepository()
        with patch.object(repo.redis_storage, 'get',
                          AsyncMock(return_value=_MOD_DATA)), \
             patch.object(repo.storage, 'get_by_id',
                          AsyncMock()) as mock_db:
            result = await repo.get_result_by_id(1)

        mock_db.assert_not_awaited()
        assert result is not None
        assert result.id == 1

    async def test_cache_miss_saves_to_cache(self):
        repo = ModerationRepository()
        with patch.object(repo.redis_storage, 'get',
                          AsyncMock(return_value=None)), \
             patch.object(repo.storage, 'get_by_id',
                          AsyncMock(return_value=_MOD_DATA)) as mock_db, \
             patch.object(repo.redis_storage, 'set',
                          AsyncMock()) as mock_set:
            result = await repo.get_result_by_id(1)

        mock_db.assert_awaited_once_with(1)
        mock_set.assert_awaited_once_with(1, _MOD_DATA)
        assert result.id == 1

    async def test_cache_invalidated_on_update_result(self):
        repo = ModerationRepository()
        with patch.object(repo.storage, 'update_result', AsyncMock()), \
             patch.object(repo.redis_storage, 'delete',
                          AsyncMock()) as mock_del:
            await repo.update_result(1, "completed", True, 0.9, None)

        mock_del.assert_awaited_once_with(1)

    @pytest.mark.parametrize("task_id,status,is_violation,prob,error", [
        (1, "completed", True, 0.9, None),
        (2, "failed", None, None, "error"),
    ])
    async def test_update_result_passes_correct_args(self, task_id, status,
                                                      is_violation, prob, error):
        repo = ModerationRepository()
        with patch.object(repo.storage, 'update_result',
                          AsyncMock()) as mock_update, \
             patch.object(repo.redis_storage, 'delete', AsyncMock()):
            await repo.update_result(task_id, status, is_violation, prob, error)

        mock_update.assert_awaited_once_with(
            task_id=task_id,
            status=status,
            is_violation=is_violation,
            probability=prob,
            error_message=error,
        )


class TestAdvertisementRepository:

    @pytest.mark.parametrize("item_id,cached,storage_return", [
        (1, _AD_DATA, _AD_DATA),
        (2, None, {**_AD_DATA, "item_id": 2}),
        (3, None, None),
    ])
    async def test_get_by_id_with_user(self, item_id, cached, storage_return):
        if storage_return:
            storage_return = {**storage_return, "item_id": item_id}
        if cached:
            cached = {**cached, "item_id": item_id}

        repo = AdvertisementRepository()
        with patch.object(repo.redis_storage, 'get', AsyncMock(return_value=cached)), \
             patch.object(repo.storage, 'get_by_id_with_user',
                          AsyncMock(return_value=storage_return)), \
             patch.object(repo.redis_storage, 'set', AsyncMock()):
            result = await repo.get_by_id_with_user(item_id)

        if cached or storage_return:
            assert result is not None
            assert result.item_id == item_id
        else:
            assert result is None


class TestAuthRepository:

    @pytest.mark.parametrize("refresh_token,stored_id", [
        ("token123", 42),
        ("invalid", None),
    ])
    async def test_get_user_id_by_refresh_token(self, refresh_token, stored_id):
        repo = AuthRepository()
        with patch.object(repo.redis_storage, 'get',
                          AsyncMock(return_value=str(stored_id)
                                    if stored_id is not None else None)):
            result = await repo.get_user_id_by_refresh_token(refresh_token)

        assert isinstance(result, UserIdResponse)
        assert result.user_id == stored_id

    @pytest.mark.parametrize("user_id,new_token,ttl,old_token", [
        (1, "new", timedelta(days=1), "old"),
        (2, "new2", timedelta(hours=12), None),
    ])
    async def test_update_refresh_token(self, user_id, new_token, ttl, old_token):
        repo = AuthRepository()
        with patch.object(repo.redis_storage, 'delete',
                          AsyncMock()) as mock_del, \
             patch.object(repo.redis_storage, 'set', AsyncMock()) as mock_set:
            result = await repo.update_refresh_token(user_id, new_token, ttl, old_token)

        assert isinstance(result, TokenUpdateResponse)
        assert result.success is True
        if old_token:
            mock_del.assert_awaited_once_with(old_token)
        mock_set.assert_awaited_once_with(
            user_id=user_id, refresh_token=new_token, ttl=ttl
        )


class TestAccountRepository:

    @pytest.mark.parametrize("account_id,cached,storage_return,should_raise", [
        (1, {"id": 1, "login": "bob", "password": "hashed_pw", "is_blocked": False}, None, False),
        (2, None, {"id": 2, "login": "bob", "password": "hashed_pw", "is_blocked": False}, False),
        (3, None, None, True),
    ])
    async def test_get_by_id(self, account_id, cached, storage_return, should_raise):
        repo = AccountRepository()
        with patch.object(repo.redis_storage, 'get', AsyncMock(return_value=cached)), \
             patch.object(repo.storage, 'get_by_id', AsyncMock(return_value=storage_return)), \
             patch.object(repo.redis_storage, 'set', AsyncMock()):
            if should_raise:
                with pytest.raises(UserNotFoundError):
                    await repo.get_by_id(account_id)
            else:
                result = await repo.get_by_id(account_id)
                assert result is not None
                assert isinstance(result, AccountModel)


class TestAccountRepositoryAllMethods:

    async def test_create_returns_account_model(self):
        repo = AccountRepository()
        raw = {"id": 1, "login": "alice", "password": "hashed_pw", "is_blocked": False}
        with patch.object(repo.storage, 'create', AsyncMock(return_value=raw)) as mock_create, \
             patch.object(repo.redis_storage, 'set', AsyncMock()):
            result = await repo.create("alice", "plainpass")

        mock_create.assert_awaited_once_with("alice", "plainpass")
        assert isinstance(result, AccountModel)
        assert result.id == 1
        assert result.login == "alice"

    @pytest.mark.parametrize("account_id,raw,should_raise", [
        (1, {"id": 1, "login": "bob", "password": "hashed_pw", "is_blocked": False}, False),
        (2, None, True),
    ])
    async def test_get_by_id(self, account_id, raw, should_raise):
        repo = AccountRepository()
        with patch.object(repo.redis_storage, 'get', AsyncMock(return_value=None)), \
             patch.object(repo.storage, 'get_by_id', AsyncMock(return_value=raw)), \
             patch.object(repo.redis_storage, 'set', AsyncMock()):
            if should_raise:
                with pytest.raises(UserNotFoundError):
                    await repo.get_by_id(account_id)
            else:
                result = await repo.get_by_id(account_id)
                assert isinstance(result, AccountModel)
                assert result.id == account_id

    @pytest.mark.parametrize("account_id,raw,should_raise", [
        (1, {"id": 1, "login": "carol", "password": "hashed_pw", "is_blocked": False}, False),
        (2, None, True),
    ])
    async def test_delete(self, account_id, raw, should_raise):
        repo = AccountRepository()
        with patch.object(repo.storage, 'delete',
                          AsyncMock(return_value=raw)) as mock_del, \
             patch.object(repo.redis_storage, 'delete', AsyncMock()):
            if should_raise:
                with pytest.raises(UserNotFoundError):
                    await repo.delete(account_id)
            else:
                result = await repo.delete(account_id)
                assert isinstance(result, AccountModel)
                assert result.id == account_id

            mock_del.assert_awaited_once_with(account_id)

    @pytest.mark.parametrize("account_id,raw,should_raise", [
        (1, {"id": 1, "login": "dave", "password": "hashed_pw", "is_blocked": True}, False),
        (2, None, True),
    ])
    async def test_block(self, account_id, raw, should_raise):
        repo = AccountRepository()
        with patch.object(repo.storage, 'block',
                          AsyncMock(return_value=raw)) as mock_block, \
             patch.object(repo.redis_storage, 'delete', AsyncMock()):
            if should_raise:
                with pytest.raises(UserNotFoundError):
                    await repo.block(account_id)
            else:
                result = await repo.block(account_id)
                assert isinstance(result, AccountModel)
                assert result.is_blocked is True

            mock_block.assert_awaited_once_with(account_id)

    @pytest.mark.parametrize("login,password,raw,should_raise", [
        ("eve", "correct", {"id": 3, "login": "eve", "password": "hashed_pw", "is_blocked": False}, False),
        ("eve", "wrong", None, True),
    ])
    async def test_get_by_login_and_password(self, login, password, raw, should_raise):
        repo = AccountRepository()
        with patch.object(repo.storage, 'get_by_login_and_password',
                          AsyncMock(return_value=raw)) as mock_get:
            if should_raise:
                with pytest.raises(UserNotFoundError):
                    await repo.get_by_login_and_password(login, password)
            else:
                result = await repo.get_by_login_and_password(login, password)
                assert isinstance(result, AccountModel)
                assert result.login == login

            mock_get.assert_awaited_once_with(login, password)