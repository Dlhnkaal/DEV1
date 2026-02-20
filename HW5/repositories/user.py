import logging
import json
from datetime import timedelta
from dataclasses import dataclass, field
from typing import Optional, List, Mapping, Any, Sequence

from clients.postgres import get_pg_connection
from clients.redis import get_redis_connection
from models.user import UserInDB

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UserPostgresStorage:
    async def create(self, login: str, password: str, email: str, is_verified_seller: bool) -> Mapping[str, Any]:
        logger.info("Creating user name=%s, email=%s", login, email)
        query = """
            INSERT INTO users (login, password, email, is_verified_seller)
            VALUES ($1, $2, $3, $4)
            RETURNING id, login, password, email, is_verified_seller, created_at, updated_at
        """
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, login, password, email, is_verified_seller)
            return dict(row) if row else None

    async def get_by_id(self, user_id: int) -> Optional[Mapping[str, Any]]:
        logger.info("Selecting user by id=%s", user_id)
        query = """
            SELECT id, login, password, email, is_verified_seller, created_at, updated_at
            FROM users
            WHERE id = $1
        """
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, user_id)
            if row:
                return dict(row)
            logger.warning("User not found, id=%s", user_id)
            return None

    async def get_all(self) -> Sequence[Mapping[str, Any]]:
        logger.info("Selecting all users")
        query = """
            SELECT id, login, password, email, is_verified_seller, created_at, updated_at
            FROM users
            ORDER BY created_at DESC
        """
        async with get_pg_connection() as connection:
            rows = await connection.fetch(query)
            return [dict(row) for row in rows]


@dataclass(frozen=True)
class UserRedisStorage:
    """Кэш 1 день, так как данные редко меняются, но при изменении инвалидируем"""
    _TTL: timedelta = timedelta(days=1)
    _KEY_PREFIX: str = "user:"

    def _key(self, user_id: int) -> str:
        return f"{self._KEY_PREFIX}{user_id}"

    async def set(self, user_id: int, data: Mapping[str, Any]) -> None:
        async with get_redis_connection() as conn:
            await conn.setex(
                name=self._key(user_id),
                time=self._TTL,
                value=json.dumps(data, default=str)
            )

    async def get(self, user_id: int) -> Optional[Mapping[str, Any]]:
        async with get_redis_connection() as conn:
            raw = await conn.get(self._key(user_id))
            if raw:
                return json.loads(raw)
            return None

    async def delete(self, user_id: int) -> None:
        async with get_redis_connection() as conn:
            await conn.delete(self._key(user_id))


@dataclass
class UserRepository:
    storage: UserPostgresStorage = field(default_factory=UserPostgresStorage)
    redis_storage: UserRedisStorage = field(default_factory=UserRedisStorage)

    async def create(self, login: str, password: str, email: str, is_verified_seller: bool) -> UserInDB:
        raw_user = await self.storage.create(
            login=login,
            password=password,
            email=email,
            is_verified_seller=is_verified_seller
        )
        if raw_user:
            await self.redis_storage.set(raw_user["id"], raw_user)
            return UserInDB(**raw_user)
        return None

    async def get_by_id(self, user_id: int) -> Optional[UserInDB]:
        cached = await self.redis_storage.get(user_id)
        if cached:
            logger.info(f"Cache hit for user id={user_id}")
            return UserInDB(**cached)

        raw_user = await self.storage.get_by_id(user_id)
        if raw_user:
            await self.redis_storage.set(user_id, raw_user)
            return UserInDB(**raw_user)

        return None

    async def get_all(self) -> List[UserInDB]:
        raw_users = await self.storage.get_all()
        return [UserInDB(**row) for row in raw_users]