import pytest
from datetime import datetime
from unittest.mock import AsyncMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from models.advertisement import AdvertisementInDB, AdvertisementWithUserBase
from repositories.advertisement import AdvertisementRepository


@pytest.mark.asyncio
class TestAdvertisementRepository:

    @pytest.mark.parametrize("seller_id,name,description,category,images_qty,expected_id", [
        (1, "Ad1", "Desc1", 5, 2, 1),
        (2, "Ad2", "Desc2", 10, 0, 2)
    ])
    async def test_create(self, mock_ad_storage, seller_id, name, description, category, images_qty, expected_id):
        now = datetime.now()
        mock_ad_storage.create.return_value = {
            "id": expected_id,
            "seller_id": seller_id,
            "name": name,
            "description": description,
            "category": category,
            "images_qty": images_qty,
            "created_at": now,
            "updated_at": now
        }

        repo = AdvertisementRepository(storage=mock_ad_storage)
        result = await repo.create(seller_id, name, description, category, images_qty)

        assert isinstance(result, AdvertisementInDB)
        assert result.id == expected_id
        mock_ad_storage.create.assert_called_once_with(
            seller_id=seller_id, name=name, description=description,
            category=category, images_qty=images_qty
        )

    async def test_get_by_id_with_user_cache_hit(self, mock_ad_storage, mock_ad_redis_storage):
        cached_data = {
            "item_id": 1,
            "seller_id": 1,
            "name": "cached",
            "description": "cached_desc",
            "category": 5,
            "images_qty": 2,
            "is_verified_seller": True
        }
        mock_ad_redis_storage.get.return_value = cached_data

        repo = AdvertisementRepository(storage=mock_ad_storage, redis_storage=mock_ad_redis_storage)
        result = await repo.get_by_id_with_user(1)

        assert isinstance(result, AdvertisementWithUserBase)
        assert result.name == "cached"
        mock_ad_redis_storage.get.assert_called_once_with(1)
        mock_ad_storage.get_by_id_with_user.assert_not_called()

    async def test_get_by_id_with_user_cache_miss(self, mock_ad_storage, mock_ad_redis_storage):
        raw_data = {
            "item_id": 2,
            "seller_id": 2,
            "name": "db",
            "description": "db_desc",
            "category": 10,
            "images_qty": 1,
            "is_verified_seller": False
        }
        mock_ad_redis_storage.get.return_value = None
        mock_ad_storage.get_by_id_with_user.return_value = raw_data

        repo = AdvertisementRepository(storage=mock_ad_storage, redis_storage=mock_ad_redis_storage)
        result = await repo.get_by_id_with_user(2)

        assert isinstance(result, AdvertisementWithUserBase)
        assert result.name == "db"
        mock_ad_redis_storage.get.assert_called_once_with(2)
        mock_ad_storage.get_by_id_with_user.assert_called_once_with(2)
        mock_ad_redis_storage.set.assert_called_once_with(2, raw_data)

    async def test_get_by_id_with_user_not_found(self, mock_ad_storage, mock_ad_redis_storage):
        mock_ad_redis_storage.get.return_value = None
        mock_ad_storage.get_by_id_with_user.return_value = None

        repo = AdvertisementRepository(storage=mock_ad_storage, redis_storage=mock_ad_redis_storage)
        result = await repo.get_by_id_with_user(999)

        assert result is None
        mock_ad_redis_storage.get.assert_called_once_with(999)
        mock_ad_storage.get_by_id_with_user.assert_called_once_with(999)
        mock_ad_redis_storage.set.assert_not_called()

    async def test_close_success(self, mock_ad_storage, mock_ad_redis_storage, mock_moderation_repo):
        mock_ad_storage.delete.return_value = {"id": 1}

        repo = AdvertisementRepository(
            storage=mock_ad_storage,
            redis_storage=mock_ad_redis_storage,
            moderation_repo=mock_moderation_repo
        )
        result = await repo.close(1)

        assert result is True
        mock_moderation_repo.delete_from_cache_by_item_id.assert_called_once_with(1)
        mock_ad_storage.delete.assert_called_once_with(1)
        mock_ad_redis_storage.delete.assert_called_once_with(1)

    async def test_close_not_found(self, mock_ad_storage, mock_ad_redis_storage, mock_moderation_repo):
        mock_ad_storage.delete.return_value = {}

        repo = AdvertisementRepository(
            storage=mock_ad_storage,
            redis_storage=mock_ad_redis_storage,
            moderation_repo=mock_moderation_repo
        )
        result = await repo.close(2)

        assert result is False
        mock_moderation_repo.delete_from_cache_by_item_id.assert_called_once_with(2)
        mock_ad_storage.delete.assert_called_once_with(2)
        mock_ad_redis_storage.delete.assert_not_called()