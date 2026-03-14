from dataclasses import dataclass, field
from typing import Mapping, Any, Optional
from clients.redis import get_redis_connection
from json import loads
from datetime import timedelta
from models.auth import UserIdResponse, TokenUpdateResponse

@dataclass
class AuthRedisStorage:
    async def set(self, user_id: int, refresh_token: str, ttl: timedelta) -> None:
        key = self._build_key(refresh_token)
        async with get_redis_connection() as connection:
            pipeline = connection.pipeline()
            pipeline.set(
                name=key,
                value=str(user_id),
            )
            pipeline.expire(key, ttl)
            await pipeline.execute()

    async def get(self, refresh_token: str) -> Optional[Mapping[str, Any]]:
        async with get_redis_connection() as connection:
            row = await connection.get(self._build_key(refresh_token))
            if row:
                return loads(row)
            return None

    async def delete(self, refresh_token: str) -> None:
        async with get_redis_connection() as connection:
            await connection.delete(self._build_key(refresh_token))

    @staticmethod
    def _build_key(refresh_token: str) -> str:
        return f'token:{refresh_token}'

@dataclass
class AuthRepository:
    redis_storage: AuthRedisStorage = field(default_factory=AuthRedisStorage)

    async def get_user_id_by_refresh_token(self, refresh_token: str) -> UserIdResponse:
        user_id = await self.redis_storage.get(refresh_token)
        return UserIdResponse(user_id=int(user_id) if user_id else None)

    async def update_refresh_token(
        self,
        user_id: int,
        new_refresh_token: str,
        ttl: timedelta,
        old_refresh_token: Optional[str] = None,
    ) -> TokenUpdateResponse:
        if old_refresh_token:
            await self.redis_storage.delete(old_refresh_token)

        await self.redis_storage.set(
            user_id=user_id,
            refresh_token=new_refresh_token,
            ttl=ttl,
        )
        return TokenUpdateResponse(success=True)
