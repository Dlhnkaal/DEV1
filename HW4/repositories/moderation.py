import logging
from dataclasses import dataclass, field
from typing import Optional, Mapping, Any

from clients.postgres import get_pg_connection

from models.moderation import (
    ModerationResultInDB, 
    ModerationResultUpdate,
    AsyncPredictRequest,     
    AsyncTaskStatusRequest   
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


@dataclass
class ModerationRepository:
    storage: ModerationPostgresStorage = field(default_factory=ModerationPostgresStorage)

    async def check_advertisement_exists(self, dto: AsyncPredictRequest) -> bool:
        return await self.storage.check_advertisement_exists(dto.item_id)

    async def create_pending(self, dto: AsyncPredictRequest) -> Optional[ModerationResultInDB]:
        raw = await self.storage.create_pending(dto.item_id)
        return ModerationResultInDB(**raw) if raw else None

    async def get_result_by_id(self, dto: AsyncTaskStatusRequest) -> Optional[ModerationResultInDB]:
        raw = await self.storage.get_by_id(dto.task_id)
        return ModerationResultInDB(**raw) if raw else None

    async def update_result(self, dto: AsyncTaskStatusRequest, update_data: ModerationResultUpdate) -> None:
        await self.storage.update_result(
            task_id=dto.task_id,
            status=update_data.status,
            is_violation=update_data.is_violation,
            probability=update_data.probability,
            error_message=update_data.error_message
        )