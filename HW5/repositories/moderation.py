import logging
import json
from datetime import timedelta
from dataclasses import dataclass, field
from typing import Optional, Mapping, Any, List

from clients.postgres import get_pg_connection
from clients.redis import get_redis_connection

from models.moderation import (
    ModerationResultInDB,
    ModerationResultUpdate,
    AsyncPredictRequest,
    AsyncTaskStatusRequest,
    TaskIdList
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModerationPostgresStorage:

    async def create_pending(self, item_id: int) -> Optional[Mapping[str, Any]]:
        logger.info("Creating pending moderation for item_id=%s", item_id)
        query = """
            INSERT INTO moderation_results (item_id, status, created_at)
            VALUES ($1, 'pending', NOW())
            RETURNING id, item_id, status, created_at, 
                      is_violation, probability, error_message, processed_at
        """
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, item_id)
            if row:
                logger.info("Pending moderation created, id=%s", row["id"])
                return dict(row)
            return None

    async def check_advertisement_exists(self, item_id: int) -> bool:
        query = "SELECT 1 FROM advertisements WHERE id = $1"
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, item_id)
            return row is not None

    async def get_by_id(self, task_id: int) -> Optional[Mapping[str, Any]]:
        logger.info("Getting moderation result for task_id=%s", task_id)
        query = """
            SELECT id, item_id, status, created_at, 
                   is_violation, probability, error_message, processed_at
            FROM moderation_results 
            WHERE id = $1
        """
        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, task_id)
            return dict(row) if row else None

    async def update_result(
        self,
        task_id: int,
        status: str,
        is_violation: Optional[bool],
        probability: Optional[float],
        error_message: Optional[str]
    ) -> None:
        logger.info("Updating moderation result for task_id=%s, status=%s", task_id, status)
        query = """
            UPDATE moderation_results
            SET status = $2, 
                is_violation = $3, 
                probability = $4, 
                error_message = $5, 
                processed_at = NOW()
            WHERE id = $1
        """
        async with get_pg_connection() as connection:
            await connection.execute(
                query, task_id, status, is_violation, probability, error_message
            )

    async def get_task_ids_by_item_id(self, item_id: int) -> List[int]:
        logger.info("Getting moderation task ids for item_id=%s", item_id)
        query = "SELECT id FROM moderation_results WHERE item_id = $1"
        async with get_pg_connection() as connection:
            rows = await connection.fetch(query, item_id)
            return [row["id"] for row in rows]


@dataclass(frozen=True)
class ModerationRedisStorage:
    """Кэш 1 час, так как после обработки данные не меняются"""
    _TTL: timedelta = timedelta(hours=1)
    _KEY_PREFIX: str = "moderation:"

    def _key(self, task_id: int) -> str:
        return f"{self._KEY_PREFIX}{task_id}"

    async def set(self, task_id: int, data: Mapping[str, Any]) -> None:
        async with get_redis_connection() as conn:
            await conn.setex(
                name=self._key(task_id),
                time=self._TTL,
                value=json.dumps(data, default=str)
            )

    async def get(self, task_id: int) -> Optional[Mapping[str, Any]]:
        async with get_redis_connection() as conn:
            raw = await conn.get(self._key(task_id))
            if raw:
                return json.loads(raw)
            return None

    async def delete(self, task_id: int) -> None:
        async with get_redis_connection() as conn:
            await conn.delete(self._key(task_id))


@dataclass
class ModerationRepository:
    storage: ModerationPostgresStorage = field(default_factory=ModerationPostgresStorage)
    redis_storage: ModerationRedisStorage = field(default_factory=ModerationRedisStorage)

    async def check_advertisement_exists(self, dto: AsyncPredictRequest) -> bool:
        return await self.storage.check_advertisement_exists(dto.item_id)

    async def create_pending(self, dto: AsyncPredictRequest) -> Optional[ModerationResultInDB]:
        raw = await self.storage.create_pending(dto.item_id)
        return ModerationResultInDB(**raw) if raw else None

    async def get_result_by_id(self, dto: AsyncTaskStatusRequest) -> Optional[ModerationResultInDB]:
        cached = await self.redis_storage.get(dto.task_id)
        if cached:
            logger.info(f"Cache hit for task_id={dto.task_id}")
            return ModerationResultInDB(**cached)

        raw = await self.storage.get_by_id(dto.task_id)
        if raw:
            await self.redis_storage.set(dto.task_id, raw)
            return ModerationResultInDB(**raw)

        return None

    async def update_result(self, dto: AsyncTaskStatusRequest, update_data: ModerationResultUpdate) -> None:
        await self.storage.update_result(
            task_id=dto.task_id,
            status=update_data.status,
            is_violation=update_data.is_violation,
            probability=update_data.probability,
            error_message=update_data.error_message
        )
        await self.redis_storage.delete(dto.task_id)

    async def get_task_ids_by_item_id(self, item_id: int) -> TaskIdList:
        task_ids = await self.storage.get_task_ids_by_item_id(item_id)
        return TaskIdList(task_ids=task_ids)

    async def delete_from_cache_by_item_id(self, item_id: int) -> None:
        task_ids_dto = await self.get_task_ids_by_item_id(item_id)
        for task_id in task_ids_dto.task_ids:
            await self.redis_storage.delete(task_id)