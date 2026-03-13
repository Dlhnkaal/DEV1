from fastapi import APIRouter, Response, Request
from pydantic import BaseModel
from dependencies import AuthServiceDepend
from errors import UnauthorizedError

router = APIRouter()

class LoginRequest(BaseModel):
    login: str
    password: str

@router.post("/login")
async def login_handler(
    response: Response,
    request: LoginRequest,
    auth_service: AuthServiceDepend
):
    access_token, refresh_token = await auth_service.login(request.login, request.password)
    
    response.set_cookie(key="x-user-token", value=access_token, httponly=True)
    response.set_cookie(key="x-refresh-token", value=refresh_token, httponly=True)
    
    return {"message": "Authorization was successful"}


@router.post("/refresh")
async def refresh_handler(
    request: Request,
    response: Response,
    auth_service: AuthServiceDepend
):
    old_refresh_token = request.cookies.get('x-refresh-token')
    if not old_refresh_token:
        raise UnauthorizedError()
        
    access_token, new_refresh_token = await auth_service.refresh_token(old_refresh_token)
    
    response.set_cookie(key="x-user-token", value=access_token, httponly=True)
    response.set_cookie(key="x-refresh-token", value=new_refresh_token, httponly=True)
    
    return {"message": "Tokens refreshed successfully"}