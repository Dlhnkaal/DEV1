import logging
from typing import Optional
from repositories.moderation import ModerationRepository
from clients.kafka import ModerationProducer
from models.moderation import (
    AsyncPredictRequest, 
    AsyncTaskStatusRequest,
    ModerationResultInDB,
    ModerationTaskResult  
)
from errors import AdvertisementNotFoundError, ModerationTaskNotFoundError

logger = logging.getLogger(__name__)

class AsyncModerationService:
    def __init__(self):
        self.repo = ModerationRepository()
        self.producer = ModerationProducer()
        
    async def start(self):
        await self.producer.start()

    async def start_moderation(self, dto: AsyncPredictRequest) -> ModerationTaskResult:
        item_id = dto.item_id
        
        exists = await self.repo.check_advertisement_exists(item_id)
        if not exists:
            raise AdvertisementNotFoundError(f"Advertisement {item_id} not found")
        
        moderation_entry = await self.repo.create_pending(item_id)
        if not moderation_entry:
            raise Exception("Failed to create moderation entry")
            
        task_id = moderation_entry.id
        await self.producer.send_moderation_request(task_id, item_id)
        
        return ModerationTaskResult(
            task_id=task_id,
            status="pending",
            message="Moderation request accepted"
        )

    async def get_moderation_status(self, dto: AsyncTaskStatusRequest) -> ModerationResultInDB:
        result = await self.repo.get_result_by_id(dto.task_id)
        
        if result is None:
            raise ModerationTaskNotFoundError(f"Moderation task {dto.task_id} not found")
            
        return result

    async def close(self):
        await self.producer.stop()