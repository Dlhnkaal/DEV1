import pytest
from datetime import datetime
from unittest.mock import AsyncMock
from models.advertisement import AdvertisementInDB, AdvertisementWithUserBase
from repositories.advertisement import AdvertisementRepository
from errors import AdvertisementNotFoundError


@pytest.mark.asyncio
class TestAdvertisementRepository:

    @pytest.mark.parametrize("seller_id,name,description,category,images_qty,expected_id", [
        (1, "Ad1", "Desc1", 5, 2, 1),
        (2, "Ad2", "Desc2", 10, 0, 2)])
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
        assert result.seller_id == seller_id
        assert result.name == name
        assert result.description == description
        assert result.category == category
        assert result.images_qty == images_qty
        assert result.created_at == now
        assert result.updated_at == now
        
        # Проверяем, что storage.create был вызван с правильными аргументами
        mock_ad_storage.create.assert_called_once_with(
            seller_id=seller_id,
            name=name,
            description=description,
            category=category,
            images_qty=images_qty
        )

    @pytest.mark.parametrize("item_id,expected_seller_id,expected_name", [
        (1, 1, "Test1"),
        (2, 2, "Test2")])
    async def test_get_by_id_with_user_success(self, mock_ad_storage, item_id, expected_seller_id, expected_name):
        mock_ad_storage.get_by_id_with_user.return_value = {
            "item_id": item_id,
            "seller_id": expected_seller_id,
            "name": expected_name,
            "description": "desc",
            "category": 1,
            "images_qty": 1,
            "is_verified_seller": True
        }
        
        repo = AdvertisementRepository(storage=mock_ad_storage)
        result = await repo.get_by_id_with_user(item_id)
        
        assert isinstance(result, AdvertisementWithUserBase)
        assert result.item_id == item_id
        assert result.seller_id == expected_seller_id
        assert result.name == expected_name
        assert result.description == "desc"
        assert result.category == 1
        assert result.images_qty == 1
        assert result.is_verified_seller is True
        
        mock_ad_storage.get_by_id_with_user.assert_called_once_with(item_id)

    async def test_get_by_id_with_user_not_found(self, mock_ad_storage):
        mock_ad_storage.get_by_id_with_user.return_value = None
        repo = AdvertisementRepository(storage=mock_ad_storage)
        
        result = await repo.get_by_id_with_user(999)
        assert result is None
        mock_ad_storage.get_by_id_with_user.assert_called_once_with(999)

    @pytest.mark.parametrize("mock_return,expected_count", [
        ([], 0),
        ([{
            "id": 1,
            "seller_id": 1,
            "name": "Ad1",
            "description": "Desc1",
            "category": 5,
            "images_qty": 2,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }], 1),
        ([
            {
                "id": 1,
                "seller_id": 1,
                "name": "Ad1",
                "description": "Desc1",
                "category": 5,
                "images_qty": 2,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            },
            {
                "id": 2,
                "seller_id": 2,
                "name": "Ad2",
                "description": "Desc2",
                "category": 10,
                "images_qty": 0,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
        ], 2)
    ])
    async def test_get_all(self, mock_ad_storage, mock_return, expected_count):
        mock_ad_storage.get_all.return_value = mock_return
        repo = AdvertisementRepository(storage=mock_ad_storage)
        
        result = await repo.get_all()
        
        assert len(result) == expected_count
        if expected_count > 0:
            assert all(isinstance(ad, AdvertisementInDB) for ad in result)
            # Проверяем соответствие данных
            for i, ad in enumerate(result):
                assert ad.id == mock_return[i]["id"]
                assert ad.seller_id == mock_return[i]["seller_id"]
                assert ad.name == mock_return[i]["name"]
        
        mock_ad_storage.get_all.assert_called_once()

    @pytest.mark.parametrize("item_id,deleted_exists", [
        (1, True),
        (2, False)])
    async def test_delete(self, mock_ad_storage, item_id, deleted_exists):
        mock_ad_storage.delete.return_value = {"id": item_id} if deleted_exists else {}
        
        repo = AdvertisementRepository(storage=mock_ad_storage)
        result = await repo.delete(item_id)
        
        assert result is deleted_exists
        mock_ad_storage.delete.assert_called_once_with(item_id)