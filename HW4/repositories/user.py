import logging
from dataclasses import dataclass
from typing import Optional, List, Mapping, Any, Sequence

from clients.postgres import get_pg_connection
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

@dataclass
class UserRepository:
    storage: UserPostgresStorage = UserPostgresStorage()

    async def create(self, login: str, password: str, email: str, is_verified_seller: bool) -> UserInDB:
        raw_user = await self.storage.create(
            login=login,
            password=password,
            email=email,
            is_verified_seller=is_verified_seller
        )
        return UserInDB(**raw_user) if raw_user else None

    async def get_by_id(self, user_id: int) -> Optional[UserInDB]:
        raw_user = await self.storage.get_by_id(user_id)
        return UserInDB(**raw_user) if raw_user else None

    async def get_all(self) -> List[UserInDB]:
        raw_users = await self.storage.get_all()
        return [UserInDB(**row) for row in raw_users]