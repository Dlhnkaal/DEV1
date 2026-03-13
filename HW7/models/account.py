from pydantic import BaseModel, Field

class AccountModel(BaseModel):
    id: int = Field()
    login: str = Field(min_length=1, max_length=1000)
    password: str = Field(min_length=8, max_length=1000)
    is_blocked: bool = False