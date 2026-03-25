from typing import Annotated
from fastapi import Depends, Request

from services.advertisement import AdvertisementMLService
from services.moderation import AsyncModerationService
from services.auth import AuthService
from models.account import AccountModel
from errors import UnAuthorizedError

def get_ml_service(request: Request) -> AdvertisementMLService:
    return request.app.state.ml_service

def get_moderation_service(request: Request) -> AsyncModerationService:
    return request.app.state.moderation_service


def auth_service() -> AuthService:
    return AuthService()

async def get_current_account(
    request: Request, 
    auth_srv: AuthService = Depends(auth_service)
) -> AccountModel:
    x_user_token = request.cookies.get('x-user-token')
    if not x_user_token:
        raise UnAuthorizedError()
    return await auth_srv.verify(x_user_token)


MLServiceDepend = Annotated[AdvertisementMLService, Depends(get_ml_service)]
ModerationServiceDepend = Annotated[AsyncModerationService, Depends(get_moderation_service)]
AuthServiceDepend = Annotated[AuthService, Depends(auth_service)]
AuthDepend = Annotated[AccountModel, Depends(get_current_account)]
