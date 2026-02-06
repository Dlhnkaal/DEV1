from dataclasses import dataclass
from typing import List, Optional
from clients.postgres import get_pg_connection
from errors import AdvertisementNotFoundError
from models.advertisement import AdvertisementCreate, AdvertisementInDB, AdvModel

@dataclass
class AdvertisementRepository:
    
    async def create(self, ad_data: AdvertisementCreate) -> AdvertisementInDB:
        query = """
            INSERT INTO advertisements (seller_id, name, description, category, images_qty)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, seller_id, name, description, category, images_qty, 
                      created_at, updated_at
        """
        
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(
                query,
                ad_data.seller_id,
                ad_data.name,
                ad_data.description,
                ad_data.category,
                ad_data.images_qty)
            
            if not row:
                raise Exception("Failed to create advertisement")
            
            return AdvertisementInDB(**dict(row))
    
    async def get_by_id(self, item_id: int) -> AdvModel:
        query = """
            SELECT 
                a.id, a.seller_id, a.name, a.description, 
                a.category, a.images_qty, a.created_at, a.updated_at,
                u.is_verified_seller
            FROM advertisements a
            JOIN users u ON a.seller_id = u.id
            WHERE a.id = $1
        """
        
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, item_id)
            
            if not row:
                raise AdvertisementNotFoundError(f"Advertisement with id {item_id} not found")
            
            data = dict(row)
            return AdvModel(
                id=data['id'],
                seller_id=data['seller_id'],
                name=data['name'],
                description=data['description'],
                category=data['category'],
                images_qty=data['images_qty'],
                is_verified_seller=data['is_verified_seller'])
    
    async def get_by_seller(self, seller_id: int) -> List[AdvertisementInDB]:
        query = """
            SELECT id, seller_id, name, description, category, images_qty, 
                   created_at, updated_at
            FROM advertisements
            WHERE seller_id = $1
            ORDER BY created_at DESC
        """
        
        async with get_pg_connection() as connection:
            rows = await connection.fetch(query, seller_id)
            return [AdvertisementInDB(**dict(row)) for row in rows]
    
    async def get_all(self) -> List[AdvertisementInDB]:
        query = """
            SELECT id, seller_id, name, description, category, images_qty, 
                   created_at, updated_at
            FROM advertisements
            ORDER BY created_at DESC
        """
        
        async with get_pg_connection() as connection:
            rows = await connection.fetch(query)
            return [AdvertisementInDB(**dict(row)) for row in rows]
    
    async def delete(self, item_id: int) -> bool:
        query = "DELETE FROM advertisements WHERE id = $1 RETURNING id"
        
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, item_id)
            return bool(row)