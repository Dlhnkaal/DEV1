import hashlib
from dataclasses import dataclass, field
from typing import Mapping, Any, Optional

from clients.postgres import get_pg_connection
from errors import UserNotFoundError
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
class AccountRepository:
    storage: AccountPostgresStorage = field(default_factory=AccountPostgresStorage)

    async def create(self, login: str, password: str) -> AccountModel:
        raw = await self.storage.create(login, password)
        return AccountModel(**raw)

    async def get_by_id(self, account_id: int) -> AccountModel:
        raw = await self.storage.get_by_id(account_id)
        if not raw:
            raise UserNotFoundError()
        return AccountModel(**raw)

    async def delete(self, account_id: int) -> AccountModel:
        raw = await self.storage.delete(account_id)
        if not raw:
            raise UserNotFoundError()
        return AccountModel(**raw)

    async def block(self, account_id: int) -> AccountModel:
        raw = await self.storage.block(account_id)
        if not raw:
            raise UserNotFoundError()
        return AccountModel(**raw)

    async def get_by_login_and_password(self, login: str, password: str) -> AccountModel:
        raw = await self.storage.get_by_login_and_password(login, password)
        if not raw:
            raise UserNotFoundError()
        return AccountModel(**raw)
