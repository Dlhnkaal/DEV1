import hashlib
from dataclasses import dataclass, field
from typing import Mapping, Any, Optional
import json

from clients.postgres import get_pg_connection
from clients.redis import get_redis_connection
from errors import UserNotFoundError
from datetime import timedelta
from models.account import AccountModel

def hash_password(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()

@dataclass
class AccountPostgresStorage:
    async def create(self, login: str, password: str) -> Mapping[str, Any]:
        query = '''
        INSERT INTO account (login, password)
        VALUES ($1, $2)
        RETURNING *
        '''
        hashed_password = hash_password(password)
        async with get_pg_connection() as connection:
            return dict(await connection.fetchrow(query, login, hashed_password))

    async def get_by_id(self, account_id: int) -> Optional[Mapping[str, Any]]:
        query = '''
        SELECT * FROM account
        WHERE id = $1::INTEGER
        LIMIT 1
        '''
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, account_id)
            if row:
                return dict(row)
            return None

    async def delete(self, account_id: int) -> Optional[Mapping[str, Any]]:
        query = '''
        DELETE FROM account
        WHERE id = $1::INTEGER
        RETURNING *
        '''
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, account_id)
            if row:
                return dict(row)
            return None

    async def block(self, account_id: int) -> Optional[Mapping[str, Any]]:
        query = '''
        UPDATE account
        SET is_blocked = TRUE
        WHERE id = $1::INTEGER
        RETURNING *
        '''
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, account_id)
            if row:
                return dict(row)
            return None

    async def get_by_login_and_password(self, login: str, password: str) -> Optional[Mapping[str, Any]]:
        query = '''
        SELECT * FROM account
        WHERE login = $1::TEXT AND password = $2::TEXT
        LIMIT 1
        '''
        hashed_password = hash_password(password)
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, login, hashed_password)
            if row:
                return dict(row)
            return None
        
@dataclass
class AccountRedisStorage:
    _TTL: timedelta = timedelta(hours=1)
    _KEY_PREFIX: str = "account:"

    def _key(self, account_id: int) -> str:
        return f"{self._KEY_PREFIX}{account_id}"

    async def set(self, account_id: int, data: Mapping[str, Any]) -> None:
        async with get_redis_connection() as conn:
            await conn.setex(
                name=self._key(account_id),
                time=self._TTL,
                value=json.dumps(data)
            )

    async def get(self, account_id: int) -> Optional[Mapping[str, Any]]:
        async with get_redis_connection() as conn:
            raw = await conn.get(self._key(account_id))
            if raw:
                return json.loads(raw)
            return None

    async def delete(self, account_id: int) -> None:
        async with get_redis_connection() as conn:
            await conn.delete(self._key(account_id))

@dataclass
class AccountRepository:
    storage: AccountPostgresStorage = field(default_factory=AccountPostgresStorage)
    redis_storage: AccountRedisStorage = field(default_factory=AccountRedisStorage)

    async def create(self, login: str, password: str) -> AccountModel:
        raw = await self.storage.create(login, password)
        return AccountModel(**raw)

    async def get_by_id(self, account_id: int) -> AccountModel:
        cached = await self.redis_storage.get(account_id)
        if cached:
            return AccountModel(**cached)

        raw = await self.storage.get_by_id(account_id)
        if not raw:
            raise UserNotFoundError()

        await self.redis_storage.set(account_id, raw)
        return AccountModel(**raw)

    async def delete(self, account_id: int) -> AccountModel:
        raw = await self.storage.delete(account_id)
        if not raw:
            raise UserNotFoundError()
        await self.redis_storage.delete(account_id)
        return AccountModel(**raw)

    async def block(self, account_id: int) -> AccountModel:
        raw = await self.storage.block(account_id)
        if not raw:
            raise UserNotFoundError()
        await self.redis_storage.delete(account_id)
        return AccountModel(**raw)

    async def get_by_login_and_password(self, login: str, password: str) -> AccountModel:
        raw = await self.storage.get_by_login_and_password(login, password)
        if not raw:
            raise UserNotFoundError()
        return AccountModel(**raw)
