from pydantic import BaseModel, Field
from typing import Optional

class TokenPairResponse(BaseModel):
    user_token: str = Field()
    refresh_token: str = Field()

class UserIdResponse(BaseModel):
    user_id: Optional[int] = None

class TokenUpdateResponse(BaseModel):
    success: bool = Field()
