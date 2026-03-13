import hashlib
from dataclasses import dataclass
from typing import Mapping, Any

from clients.postgres import get_pg_connection
from errors import UserNotFoundError
from models.account import AccountModel

def hash_password(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()

@dataclass(frozen=True)
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

    async def get_by_id(self, account_id: int) -> Mapping[str, Any]:
        query = '''
        SELECT * FROM account
        WHERE id = $1::INTEGER
        LIMIT 1
        '''
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, account_id)
            if row:
                return dict(row)
            raise UserNotFoundError()

    async def delete(self, account_id: int) -> Mapping[str, Any]:
        query = '''
        DELETE FROM account
        WHERE id = $1::INTEGER
        RETURNING *
        '''
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, account_id)
            if row:
                return dict(row)
            raise UserNotFoundError()

    async def block(self, account_id: int) -> Mapping[str, Any]:
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
            raise UserNotFoundError()

    async def get_by_login_and_password(self, login: str, password: str) -> Mapping[str, Any]:
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
            raise UserNotFoundError()

@dataclass(frozen=True)
class AccountRepository:
    storage: AccountPostgresStorage = AccountPostgresStorage()

    async def create(self, login: str, password: str) -> AccountModel:
        raw = await self.storage.create(login, password)
        return AccountModel(**raw)

    async def get_by_id(self, account_id: int) -> AccountModel:
        raw = await self.storage.get_by_id(account_id)
        return AccountModel(**raw)

    async def delete(self, account_id: int) -> AccountModel:
        raw = await self.storage.delete(account_id)
        return AccountModel(**raw)

    async def block(self, account_id: int) -> AccountModel:
        raw = await self.storage.block(account_id)
        return AccountModel(**raw)

    async def get_by_login_and_password(self, login: str, password: str) -> AccountModel:
        raw = await self.storage.get_by_login_and_password(login, password)
        return AccountModel(**raw)