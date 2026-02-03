from pydantic import BaseModel, Field

class AdvModel(BaseModel):
    seller_id: int = Field(gt=0)
    is_verified_seller: bool
    item_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1000)
    category: int = Field(ge=0) 
    images_qty: int = Field(ge=0)