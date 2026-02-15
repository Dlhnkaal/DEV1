import logging
import logging
from dataclasses import dataclass
from typing import Optional, List, Mapping, Any, Sequence

from typing import Optional, List, Mapping, Any, Sequence

from clients.postgres import get_pg_connection
from errors import UserNotFoundError
from models.user import UserCreate, UserInDB

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UserPostgresStorage:
    async def create(self, login: str, password: str, email: str, is_verified_seller: bool) -> Mapping[str, Any]:
        logger.info("Creating user name=%s, email=%s", login, email)
        query = """
            INSERT INTO users (login, password, email, is_verified_seller)
            VALUES ($1, $2, $3)
            RETURNING id, login, password, email, is_verified_seller, created_at, updated_at
        """
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(
                query, login, email, is_verified_seller)
            if row:
                return dict(row)
            raise Exception("Failed to create user")

    async def get_by_id(self, user_id: int) -> Mapping[str, Any]:
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
            raise UserNotFoundError(f"User with id {user_id} not found")

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

    async def create(self, user_data: UserCreate) -> UserInDB:
        raw_user = await self.storage.create(
            login=user_data.login,
            password=user_data.password,
            email=user_data.email,
            is_verified_seller=user_data.is_verified_seller)
        return UserInDB(**raw_user)

    async def get_by_id(self, user_id: int) -> UserInDB:
        raw_user = await self.storage.get_by_id(user_id)
        return UserInDB(**raw_user)

    async def get_all(self) -> List[UserInDB]:
        raw_users = await self.storage.get_all()
        return [UserInDB(**row) for row in raw_users]
