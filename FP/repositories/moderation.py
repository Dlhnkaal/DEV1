import logging
import json
import time
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
from metrics import DB_QUERY_DURATION

logger = logging.getLogger(__name__)

@dataclass
class ModerationPostgresStorage:

    async def create_pending(self, item_id: int) -> Optional[Mapping[str, Any]]:
        logger.info("Creating pending moderation for item_id=%s", item_id)
        query = """
        INSERT INTO moderation_results (item_id, status, created_at)
        VALUES ($1, 'pending', NOW())
        RETURNING id, item_id, status, created_at, 
        is_violation, probability, error_message, processed_at
        """
        start_time = time.time()
        try:
            async with get_pg_connection() as connection:
                row = await connection.fetchrow(query, item_id)
                if row:
                    logger.info("Pending moderation created, id=%s", row["id"])
                    return dict(row)
                return None
        finally:
            DB_QUERY_DURATION.labels(query_type="insert").observe(time.time() - start_time)

    async def check_advertisement_exists(self, item_id: int) -> bool:
        query = "SELECT 1 FROM advertisements WHERE id = $1"
        start_time = time.time()
        try:
            async with get_pg_connection() as connection:
                row = await connection.fetchrow(query, item_id)
                return row is not None
        finally:
            DB_QUERY_DURATION.labels(query_type="select").observe(time.time() - start_time)

    async def get_by_id(self, task_id: int) -> Optional[Mapping[str, Any]]:
        logger.info("Getting moderation result for task_id=%s", task_id)
        query = """
        SELECT id, item_id, status, created_at, 
        is_violation, probability, error_message, processed_at
        FROM moderation_results 
        WHERE id = $1
        """
        start_time = time.time()
        try:
            async with get_pg_connection() as connection:
                row = await connection.fetchrow(query, task_id)
                return dict(row) if row else None
        finally:
            DB_QUERY_DURATION.labels(query_type="select").observe(time.time() - start_time)

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
        start_time = time.time()
        try:
            async with get_pg_connection() as connection:
                await connection.execute(
                    query, task_id, status, is_violation, probability, error_message
                )
        finally:
            DB_QUERY_DURATION.labels(query_type="update").observe(time.time() - start_time)

    async def get_task_ids_by_item_id(self, item_id: int) -> List[int]:
        logger.info("Getting moderation task ids for item_id=%s", item_id)
        query = "SELECT id FROM moderation_results WHERE item_id = $1"
        start_time = time.time()
        try:
            async with get_pg_connection() as connection:
                rows = await connection.fetch(query, item_id)
                return [row["id"] for row in rows]
        finally:
            DB_QUERY_DURATION.labels(query_type="select").observe(time.time() - start_time)

@dataclass
class ModerationRedisStorage:
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

    async def check_advertisement_exists(self, item_id: int) -> bool:
        return await self.storage.check_advertisement_exists(item_id)

    async def create_pending(self, item_id: int) -> Optional[ModerationResultInDB]:
        raw = await self.storage.create_pending(item_id)
        return ModerationResultInDB(**raw) if raw else None

    async def get_result_by_id(self, task_id: int) -> Optional[ModerationResultInDB]:
        cached = await self.redis_storage.get(task_id)
        if cached:
            logger.info(f"Cache hit for task_id={task_id}")
            return ModerationResultInDB(**cached)

        raw = await self.storage.get_by_id(task_id)
        if raw:
            await self.redis_storage.set(task_id, raw)
            return ModerationResultInDB(**raw)

        return None

    async def update_result(
        self,
        task_id: int,
        status: str,
        is_violation: bool,
        probability: float,
        error_message: Optional[str]
    ) -> None:
        await self.storage.update_result(
            task_id=task_id,
            status=status,
            is_violation=is_violation,
            probability=probability,
            error_message=error_message
        )
        await self.redis_storage.delete(task_id)

    async def get_task_ids_by_item_id(self, item_id: int) -> TaskIdList:
        task_ids = await self.storage.get_task_ids_by_item_id(item_id)
        return TaskIdList(task_ids=task_ids)

    async def delete_cache(self, task_id: int) -> None:
        await self.redis_storage.delete(task_id)