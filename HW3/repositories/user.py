from dataclasses import dataclass
from typing import Optional, List
from clients.postgres import get_pg_connection
from errors import UserNotFoundError
from models.user import UserCreate, UserInDB

@dataclass
class UserRepository:
    
    async def create(self, user_data: UserCreate) -> UserInDB:
        query = """
            INSERT INTO users (name, email, is_verified_seller)
            VALUES ($1, $2, $3)
            RETURNING id, name, email, is_verified_seller, created_at
        """
        
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(
                query,
                user_data.name,
                user_data.email,
                user_data.is_verified_seller)
            
            if not row:
                raise Exception("Failed to create user")
            
            return UserInDB(**dict(row))
    
    async def get_by_id(self, user_id: int) -> UserInDB:
        query = """
            SELECT id, name, email, is_verified_seller, created_at
            FROM users
            WHERE id = $1
        """
        
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, user_id)
            
            if not row:
                raise UserNotFoundError(f"User with id {user_id} not found")
            
            return UserInDB(**dict(row))
    
    async def get_by_email(self, email: str) -> Optional[UserInDB]:
        query = """
            SELECT id, name, email, is_verified_seller, created_at
            FROM users
            WHERE email = $1
        """
        
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, email)
            
            if not row:
                return None
            
            return UserInDB(**dict(row))
    
    async def get_all(self) -> List[UserInDB]:
        query = """
            SELECT id, name, email, is_verified_seller, created_at
            FROM users
            ORDER BY created_at DESC
        """
        
        async with get_pg_connection() as connection:
            rows = await connection.fetch(query)
            return [UserInDB(**dict(row)) for row in rows]