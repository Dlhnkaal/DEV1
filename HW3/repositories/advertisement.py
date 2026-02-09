import logging
from dataclasses import dataclass
from typing import Mapping, Any, Sequence, List

from clients.postgres import get_pg_connection
from errors import AdvertisementNotFoundError
from models.advertisement import AdvertisementCreate, AdvertisementInDB, AdvModel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdvertisementPostgresStorage:
    async def create(
        self,
        seller_id: int,
        name: str,
        description: str,
        category: int,
        images_qty: int) -> Mapping[str, Any]:
        logger.info(
            "Creating advertisement for seller_id=%s, category=%s", seller_id, category)
        query = """
            INSERT INTO advertisements (seller_id, name, description, category, images_qty)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, seller_id, name, description, category, images_qty,
                      created_at, updated_at
        """
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(
                query, seller_id, name, description, category, images_qty)
            if row:
                logger.info("Advertisement created successfully, id=%s", row["id"])
                return dict(row)
            logger.error("Failed to create advertisement - no row returned")
            raise Exception("Failed to create advertisement")

    async def get_by_id_with_user(self, item_id: int) -> Mapping[str, Any]:
        logger.info("Selecting advertisement with user info by id=%s", item_id)
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
            if row:
                return dict(row)
            logger.warning("Advertisement not found, id=%s", item_id)
            raise AdvertisementNotFoundError(f"Advertisement with id {item_id} not found")

    async def get_by_seller(self, seller_id: int) -> Sequence[Mapping[str, Any]]:
        logger.info("Selecting advertisements by seller_id=%s", seller_id)
        query = """
            SELECT id, seller_id, name, description, category, images_qty,
                   created_at, updated_at
            FROM advertisements
            WHERE seller_id = $1
            ORDER BY created_at DESC
        """
        async with get_pg_connection() as connection:
            rows = await connection.fetch(query, seller_id)
            return [dict(row) for row in rows]

    async def get_all(self) -> Sequence[Mapping[str, Any]]:
        logger.info("Selecting all advertisements")
        query = """
            SELECT id, seller_id, name, description, category, images_qty,
                   created_at, updated_at
            FROM advertisements
            ORDER BY created_at DESC
        """
        async with get_pg_connection() as connection:
            rows = await connection.fetch(query)
            return [dict(row) for row in rows]

    async def delete(self, item_id: int) -> Mapping[str, Any]:
        logger.info("Deleting advertisement id=%s", item_id)
        query = "DELETE FROM advertisements WHERE id = $1 RETURNING id"
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, item_id)
            if row:
                logger.info("Advertisement deleted successfully, id=%s", item_id)
                return dict(row)
            return {} 


@dataclass
class AdvertisementRepository:
    storage: AdvertisementPostgresStorage = AdvertisementPostgresStorage()

    async def create(self, ad_data: AdvertisementCreate) -> AdvertisementInDB:
        logger.info("Repository: Creating advertisement with data %s", ad_data)
        raw_ad = await self.storage.create(
            seller_id=ad_data.seller_id,
            name=ad_data.name,
            description=ad_data.description,
            category=ad_data.category,
            images_qty=ad_data.images_qty)
        return AdvertisementInDB(**raw_ad)

    async def get_by_id(self, item_id: int) -> AdvModel:
        logger.info("Repository: Getting advertisement by id=%s", item_id)
        raw_data = await self.storage.get_by_id_with_user(item_id)
        return AdvModel(**raw_data)

    async def get_by_seller(self, seller_id: int) -> List[AdvertisementInDB]:
        logger.info("Repository: Getting advertisements for seller_id=%s", seller_id)
        raw_ads = await self.storage.get_by_seller(seller_id)
        return [AdvertisementInDB(**row) for row in raw_ads]

    async def get_all(self) -> List[AdvertisementInDB]:
        logger.info("Repository: Getting all advertisements")
        raw_ads = await self.storage.get_all()
        return [AdvertisementInDB(**row) for row in raw_ads]

    async def delete(self, item_id: int) -> bool:
        logger.info("Repository: Deleting advertisement id=%s", item_id)
        res = await self.storage.delete(item_id)
        return bool(res)
