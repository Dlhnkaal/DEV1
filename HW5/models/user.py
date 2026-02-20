from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime

class UserBase(BaseModel):
    login: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8)
    email: EmailStr = Field()
    is_verified_seller: bool = Field(default=False)

class UserCreate(UserBase):
    pass

class UserInDB(UserBase):
    id: int = Field()
    created_at: datetime = Field()
    updated_at: datetime = Field()
    
    model_config = ConfigDict(from_attributes=True)

class UserModel(UserInDB):
    pass