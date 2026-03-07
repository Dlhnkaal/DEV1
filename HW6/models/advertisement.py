from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional

class AdvertisementBase(BaseModel):
    seller_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1000)
    category: int = Field(ge=0, le=100)
    images_qty: int = Field(ge=0, le=10)

class AdvertisementWithUserBase(AdvertisementBase):
    item_id: int = Field(gt=0)
    is_verified_seller: bool = Field()

class AdvertisementCreate(AdvertisementBase):
    pass

class AdvertisementInDB(AdvertisementBase):
    id: int = Field(gt=0)
    created_at: datetime = Field()
    updated_at: datetime = Field()
    
    model_config = ConfigDict(from_attributes=True)

class AdvertisementWithUserInDB(AdvertisementInDB):
    is_verified_seller: bool = Field()
    
    model_config = ConfigDict(from_attributes=True)

class AdvertisementLite(BaseModel):
    item_id: int = Field(gt=0)

class CloseAdvertisementRequest(BaseModel):
    item_id: int = Field(gt=0)

class CloseAdvertisementResponse(BaseModel):
    message: str = Field(ge=0)
    item_id: int = Field()