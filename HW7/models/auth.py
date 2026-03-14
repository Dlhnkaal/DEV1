from pydantic import BaseModel
from typing import Optional

class TokenPairResponse(BaseModel):
    user_token: str
    refresh_token: str

class UserIdResponse(BaseModel):
    user_id: Optional[int] = None

class TokenUpdateResponse(BaseModel):
    success: bool
