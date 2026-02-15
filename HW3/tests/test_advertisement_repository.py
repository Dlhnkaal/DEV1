import pytest
from datetime import datetime
now = datetime.now()
from unittest.mock import AsyncMock
from models.advertisement import AdvertisementCreate, AdvertisementInDB, AdvertisementLite, AdvertisementWithUserBase
from repositories.advertisement import AdvertisementRepository
from errors import AdvertisementNotFoundError


@pytest.mark.asyncio
class TestAdvertisementRepository:

    @pytest.mark.parametrize("input_data,expected_id", [
        (AdvertisementCreate(seller_id=1, name="Ad1", description="Desc1", category=5, images_qty=2), 1),
        (AdvertisementCreate(seller_id=2, name="Ad2", description="Desc2", category=10, images_qty=0), 2)])
    async def test_create(self, mock_ad_storage, input_data, expected_id):
        mock_ad_storage.create.return_value = {
            "id": expected_id, "seller_id": input_data.seller_id, "name": input_data.name,
            "description": input_data.description, "category": input_data.category,
            "images_qty": input_data.images_qty, "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00"}
        repo = AdvertisementRepository(storage=mock_ad_storage)
        result = await repo.create(input_data)
        assert isinstance(result, AdvertisementInDB)
        assert result.id == expected_id

    @pytest.mark.parametrize("item_id,expected_seller_id,expected_name", [(1, 1, "Test1"), (2, 2, "Test2")])
    async def test_get_by_id_with_user_success(self, mock_ad_storage, item_id, expected_seller_id, expected_name):
        mock_ad_storage.get_by_id_with_user.return_value = {
            "item_id": item_id, "seller_id": expected_seller_id, "name": expected_name,
            "description": "desc", "category": 1, "images_qty": 1, "is_verified_seller": True}
        repo = AdvertisementRepository(storage=mock_ad_storage)
        result = await repo.get_by_id_with_user(AdvertisementLite(item_id=item_id))
        assert isinstance(result, AdvertisementWithUserBase)
        assert result.seller_id == expected_seller_id
        assert result.name == expected_name

    @pytest.mark.parametrize("ad_lite", [AdvertisementLite(item_id=999)])
    async def test_get_by_id_with_user_not_found(self, mock_ad_storage, ad_lite):
        mock_ad_storage.get_by_id_with_user.side_effect = AdvertisementNotFoundError("Not found")
        repo = AdvertisementRepository(storage=mock_ad_storage)
        with pytest.raises(AdvertisementNotFoundError):
            await repo.get_by_id_with_user(ad_lite)

    @pytest.mark.parametrize("mock_return,expected_count", [
        ([], 0), ([{"id": 1, "seller_id": 1, "name": "n", "description": "d", "category": 1, "images_qty": 1, "created_at": now, "updated_at": now}], 1)])
    async def test_get_all(self, mock_ad_storage, mock_return, expected_count):
        mock_ad_storage.get_all.return_value = mock_return
        repo = AdvertisementRepository(storage=mock_ad_storage)
        result = await repo.get_all()
        assert len(result) == expected_count
        if expected_count:
            assert isinstance(result[0], AdvertisementInDB)

    @pytest.mark.parametrize("item_id,deleted_exists", [(1, True), (2, False)])
    async def test_delete(self, mock_ad_storage, item_id, deleted_exists):
        mock_ad_storage.delete.return_value = {"id": item_id} if deleted_exists else {}
        repo = AdvertisementRepository(storage=mock_ad_storage)
        result = await repo.delete(AdvertisementLite(item_id=item_id))
        assert result is deleted_exists