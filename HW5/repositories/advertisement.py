import logging
import json
from datetime import timedelta
from dataclasses import dataclass, field
from typing import Mapping, Any, Sequence, List, Optional

from clients.postgres import get_pg_connection
from clients.redis import get_redis_connection
from models.advertisement import AdvertisementWithUserBase, AdvertisementInDB
from repositories.moderation import ModerationRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdvertisementPostgresStorage:
    async def create(self, seller_id: int, name: str, description: str, category: int, images_qty: int) -> Mapping[str, Any]:
        logger.info("Creating advertisement for seller_id=%s, category=%s", seller_id, category)
        query = """
            INSERT INTO advertisements (seller_id, name, description, category, images_qty)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, seller_id, name, description, category, images_qty,
                      created_at, updated_at
        """
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, seller_id, name, description, category, images_qty)
            if row:
                logger.info("Advertisement created successfully, id=%s", row["id"])
                return dict(row)
            return None

    async def get_by_id_with_user(self, item_id: int) -> Optional[Mapping[str, Any]]:
        logger.info("Selecting advertisement with user info by id=%s", item_id)
        query = """
            SELECT 
                a.id as item_id, a.seller_id, a.name, a.description, 
                a.category, a.images_qty,
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
            return None

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


@dataclass(frozen=True)
class AdvertisementRedisStorage:
    """Кэш 1 час, так как данные редко меняются, но статус продавца может обновиться"""
    _TTL: timedelta = timedelta(hours=1)
    _KEY_PREFIX: str = "advertisement:"

    def _key(self, item_id: int) -> str:
        return f"{self._KEY_PREFIX}{item_id}"

    async def set(self, item_id: int, data: Mapping[str, Any]) -> None:
        async with get_redis_connection() as conn:
            await conn.setex(
                name=self._key(item_id),
                time=self._TTL,
                value=json.dumps(data, default=str)
            )

    async def get(self, item_id: int) -> Optional[Mapping[str, Any]]:
        async with get_redis_connection() as conn:
            raw = await conn.get(self._key(item_id))
            if raw:
                return json.loads(raw)
            return None

    async def delete(self, item_id: int) -> None:
        async with get_redis_connection() as conn:
            await conn.delete(self._key(item_id))


@dataclass
class AdvertisementRepository:
    storage: AdvertisementPostgresStorage = field(default_factory=AdvertisementPostgresStorage)
    redis_storage: AdvertisementRedisStorage = field(default_factory=AdvertisementRedisStorage)
    moderation_repo: ModerationRepository = field(default_factory=ModerationRepository)

    async def create(self, seller_id: int, name: str, description: str, category: int, images_qty: int) -> Optional[AdvertisementInDB]:
        logger.info("Repository: Creating advertisement for seller_id=%s, name=%s", seller_id, name)
        raw_ad = await self.storage.create(
            seller_id=seller_id,
            name=name,
            description=description,
            category=category,
            images_qty=images_qty
        )
        if raw_ad:
            await self.redis_storage.set(raw_ad["id"], raw_ad)
            return AdvertisementInDB(**raw_ad)
        return None

    async def get_by_id_with_user(self, item_id: int) -> Optional[AdvertisementWithUserBase]:
        logger.info("Repository: Getting advertisement by id=%s", item_id)
        cached = await self.redis_storage.get(item_id)
        if cached:
            logger.info(f"Cache hit for advertisement id={item_id}")
            return AdvertisementWithUserBase(**cached)

        raw_data = await self.storage.get_by_id_with_user(item_id)
        if raw_data:
            await self.redis_storage.set(item_id, raw_data)
            return AdvertisementWithUserBase(**raw_data)

        return None

    async def get_all(self) -> List[AdvertisementInDB]:
        logger.info("Repository: Getting all advertisements")
        raw_ads = await self.storage.get_all()
        return [AdvertisementInDB(**row) for row in raw_ads]

    async def delete(self, item_id: int) -> bool:
        logger.info("Repository: Deleting advertisement id=%s", item_id)
        res = await self.storage.delete(item_id)
        if res:
            await self.redis_storage.delete(item_id)
        return bool(res)

    async def close(self, item_id: int) -> bool:
        logger.info("Repository: Closing advertisement id=%s", item_id)
        await self.moderation_repo.delete_from_cache_by_item_id(item_id)
        res = await self.storage.delete(item_id)
        if res:
            await self.redis_storage.delete(item_id)
            return True
        return False