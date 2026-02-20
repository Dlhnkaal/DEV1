import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from services.advertisement import AdvertisementMLService
from models.advertisement import AdvertisementWithUserBase, AdvertisementLite
from errors import AdvertisementNotFoundError, ModelNotReadyError


@pytest.mark.asyncio
class TestAdvertisementMLService:

    @pytest.mark.parametrize("is_verified,images_qty,desc_len,category,expected_violation,expected_prob", 
        [(True, 5, 500, 10, False, 0.2), (False, 9, 900, 90, True, 0.8)])
    async def test_predict(self, is_verified, images_qty, desc_len, category, expected_violation, expected_prob):
        mock_model = MagicMock()
        mock_repo = AsyncMock()
        mock_model.predict_proba.return_value = np.array([[1 - expected_prob, expected_prob]])
        service = AdvertisementMLService(advertisement_repo=mock_repo)
        service._get_model = MagicMock(return_value=mock_model)
        adv = AdvertisementWithUserBase(
            item_id=1, seller_id=1, name="test", description="x" * desc_len,
            category=category, images_qty=images_qty, is_verified_seller=is_verified)
        is_violation, prob = service.predict(adv)
        assert is_violation == expected_violation
        assert prob == expected_prob

    @pytest.mark.parametrize("side_effect,expected_exception", [
        (ModelNotReadyError(""), ModelNotReadyError),
        (Exception(""), Exception)])
    async def test_predict_errors(self, side_effect, expected_exception):
        mock_repo = AsyncMock()
        mock_model = MagicMock()
        service = AdvertisementMLService(advertisement_repo=mock_repo)
        service._get_model = MagicMock(side_effect=side_effect)
        adv = AdvertisementWithUserBase(
            item_id=1, seller_id=1, name="test", description="x" * 10,
            category=10, images_qty=6, is_verified_seller=True)
        with pytest.raises(expected_exception):
            service.predict(adv)

    @pytest.mark.parametrize("is_verified,images_qty,desc_len,category,expected_violation,expected_prob", [
        (True, 5, 500, 10, False, 0.2), (False, 9, 900, 90, True, 0.8)])
    async def test_simple_predict_success(self, is_verified, images_qty, desc_len, category, expected_violation, expected_prob):
        data = {
            "item_id": 1, "seller_id": 1, "name": "test", "description": "x" * desc_len,
            "category": category, "images_qty": images_qty, "is_verified_seller": is_verified}
        mock_repo = AsyncMock()
        mock_repo.get_by_id_with_user.return_value = AdvertisementWithUserBase(**data)
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = np.array([[1 - expected_prob, expected_prob]])
        service = AdvertisementMLService(advertisement_repo=mock_repo)
        service._get_model = MagicMock(return_value=mock_model)
        adv = AdvertisementLite(item_id=1)
        is_violation, prob = await service.simple_predict(adv)
        assert is_violation == expected_violation
        assert prob == expected_prob

    @pytest.mark.parametrize("side_effect,expected_exception", [
        (AdvertisementNotFoundError(""), AdvertisementNotFoundError),
        (ModelNotReadyError(""), ModelNotReadyError),
        (Exception(""), Exception)])
    async def test_simple_predict_errors(self, side_effect, expected_exception):
        mock_repo = AsyncMock()
        mock_repo.get_by_id_with_user.side_effect = side_effect
        service = AdvertisementMLService(advertisement_repo=mock_repo)
        service._get_model = MagicMock(return_value=MagicMock())
        adv = AdvertisementLite(item_id=1)
        with pytest.raises(expected_exception):
            await service.simple_predict(adv)

    async def test_close_advertisement(self):
        mock_repo = AsyncMock()
        mock_repo.close.return_value = True
        service = AdvertisementMLService(advertisement_repo=mock_repo)
        dto = MagicMock(item_id=123)
        result = await service.close_advertisement(dto)
        assert result is True
        mock_repo.close.assert_called_once_with(123)