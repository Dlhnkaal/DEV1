import pytest
from pydantic import ValidationError
from models.advertisement import AdvertisementBase, AdvertisementWithUserBase, AdvertisementLite
from models.moderation import AsyncPredictRequest, ModerationResultInDB
from models.account import AccountModel
from datetime import datetime

class TestAdvertisementModels:
    @pytest.mark.parametrize("seller_id,name,description,category,images_qty,should_raise", [
        (1, "Valid", "Desc", 50, 5, False),
        (-1, "Valid", "Desc", 50, 5, True),
        (1, "", "Desc", 50, 5, True),
        (1, "a"*101, "Desc", 50, 5, True),
        (1, "Valid", "", 50, 5, True),
        (1, "Valid", "a"*1001, 50, 5, True),
        (1, "Valid", "Desc", -1, 5, True),
        (1, "Valid", "Desc", 101, 5, True),
        (1, "Valid", "Desc", 50, -1, True),
        (1, "Valid", "Desc", 50, 11, True),
    ])
    def test_advertisement_base(self, seller_id, name, description, category, images_qty, should_raise):
        if should_raise:
            with pytest.raises(ValidationError):
                AdvertisementBase(
                    seller_id=seller_id,
                    name=name,
                    description=description,
                    category=category,
                    images_qty=images_qty
                )
        else:
            ad = AdvertisementBase(
                seller_id=seller_id,
                name=name,
                description=description,
                category=category,
                images_qty=images_qty
            )
            assert ad.seller_id == seller_id

    @pytest.mark.parametrize("item_id,is_verified_seller", [
        (10, True),
        (1, False),  # item_id должно быть > 0
    ])
    def test_advertisement_with_user_base(self, item_id, is_verified_seller):
        ad = AdvertisementWithUserBase(
            item_id=item_id,
            seller_id=1,
            name="Name",
            description="Desc",
            category=1,
            images_qty=1,
            is_verified_seller=is_verified_seller
        )
        assert ad.item_id == item_id

    @pytest.mark.parametrize("item_id", [0, -5])
    def test_advertisement_lite_invalid(self, item_id):
        with pytest.raises(ValidationError):
            AdvertisementLite(item_id=item_id)

class TestModerationModels:
    @pytest.mark.parametrize("item_id", [1, 100])
    def test_async_predict_request_valid(self, item_id):
        req = AsyncPredictRequest(item_id=item_id)
        assert req.item_id == item_id

    @pytest.mark.parametrize("item_id", [0, -1])
    def test_async_predict_request_invalid(self, item_id):
        with pytest.raises(ValidationError):
            AsyncPredictRequest(item_id=item_id)

    @pytest.mark.parametrize("id,item_id,status,is_violation,probability,error_message,created_at,processed_at", [
        (1, 10, "pending", None, None, None, datetime.now(), None),
        (2, 20, "completed", True, 0.85, None, datetime.now(), datetime.now()),
        (3, 30, "failed", None, None, "error", datetime.now(), None),
    ])
    def test_moderation_result_in_db(self, id, item_id, status, is_violation, probability, error_message, created_at, processed_at):
        res = ModerationResultInDB(
            id=id,
            item_id=item_id,
            status=status,
            is_violation=is_violation,
            probability=probability,
            error_message=error_message,
            created_at=created_at,
            processed_at=processed_at
        )
        assert res.id == id

class TestAccountModel:
    @pytest.mark.parametrize("id,login,password,is_blocked", [
        (1, "user", "password123", False),
        (2, "admin", "secret456", True),
    ])
    def test_account_model(self, id, login, password, is_blocked):
        acc = AccountModel(id=id, login=login, password=password, is_blocked=is_blocked)
        assert acc.id == id
        assert acc.login == login
        assert acc.password == password
        assert acc.is_blocked == is_blocked