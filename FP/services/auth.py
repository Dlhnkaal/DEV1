import jwt
from dataclasses import dataclass, field
from typing import Mapping, Any
from datetime import datetime, timedelta
from contextlib import suppress

from models.account import AccountModel
from models.auth import TokenPairResponse
from repositories.account import AccountRepository
from repositories.auth import AuthRepository
from errors import UserNotFoundError, UnAuthorizedError, AuthenticationError

import os

from dotenv import load_dotenv

load_dotenv()

@dataclass
class AuthService:
    account_repo: AccountRepository = field(default_factory=AccountRepository)
    auth_repo: AuthRepository = field(default_factory=AuthRepository)
    
    _SECRET = os.getenv("_SECRET", "ya_poluchu_10_za_etu_rabotu_7777")
    _USER_TOKEN_TTL = timedelta(days=1)
    _REFRESH_USER_TOKEN_TTL = timedelta(days=7)

    async def login(self, login: str, password: str) -> TokenPairResponse:
        try:
            account = await self.account_repo.get_by_login_and_password(login, password)
            
            if account.is_blocked:
                raise AuthenticationError()
            
            user_token = self._build_user_token(account)
            refresh_token = self._build_refresh_token(account)
            
            await self.auth_repo.update_refresh_token(
                user_id=account.id,
                new_refresh_token=refresh_token,
                ttl=self._REFRESH_USER_TOKEN_TTL
            )
            
            return TokenPairResponse(user_token=user_token, refresh_token=refresh_token)
        except UserNotFoundError:
            raise AuthenticationError()

    async def refresh_token(self, old_refresh_token: str) -> TokenPairResponse:
        user_id_response = await self.auth_repo.get_user_id_by_refresh_token(old_refresh_token)
        
        if not user_id_response.user_id:
            raise UnAuthorizedError()
            
        try:
            account = await self.account_repo.get_by_id(user_id_response.user_id)
            if account.is_blocked:
                raise UnAuthorizedError()
                
            user_token = self._build_user_token(account)
            new_refresh_token = self._build_refresh_token(account)
            
            await self.auth_repo.update_refresh_token(
                user_id=account.id,
                new_refresh_token=new_refresh_token,
                ttl=self._REFRESH_USER_TOKEN_TTL,
                old_refresh_token=old_refresh_token
            )
            
            return TokenPairResponse(user_token=user_token, refresh_token=new_refresh_token)
            
        except UserNotFoundError:
            raise UnAuthorizedError()

    async def verify(self, user_token: str) -> AccountModel:
        user_payload = {}
        try:
            user_payload = self._parse_token(user_token)
        except jwt.InvalidTokenError:
            pass

        if raw_expired_at := user_payload.get('expired_at', None):
            if datetime.fromisoformat(raw_expired_at) < datetime.now():
                raise UnAuthorizedError()

        if account_id := user_payload.get('user_id', None):
            try:
                account = await self.account_repo.get_by_id(account_id)
                if account.is_blocked:
                    raise UnAuthorizedError()
                return account
            except UserNotFoundError:
                raise UnAuthorizedError()

        raise UnAuthorizedError()

    def _build_user_token(self, account: AccountModel) -> str:
        user_payload = dict(
            user_id=account.id,
            expired_at=(datetime.now() + self._USER_TOKEN_TTL).isoformat(),
        )
        return self._build_token(user_payload)

    def _build_refresh_token(self, account: AccountModel) -> str:
        refresh_payload = dict(
            user_id=account.id,
            expired_at=(datetime.now() + self._REFRESH_USER_TOKEN_TTL).isoformat(),
        )
        return self._build_token(refresh_payload)

    def _build_token(self, payload: Mapping[str, Any]) -> str:
        return jwt.encode(
            payload=payload,
            key=self._SECRET,
            algorithm='HS256',
        )

    def _parse_token(self, token: str) -> Mapping[str, Any]:
        return jwt.decode(
            jwt=token,
            key=self._SECRET,
            algorithms=['HS256'],
        )
