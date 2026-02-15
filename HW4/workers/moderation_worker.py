import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone

from aiokafka import AIOKafkaConsumer
from dotenv import load_dotenv

from services.advertisement import AdvertisementMLService
from repositories.moderation import ModerationRepository
from models.advertisement import AdvertisementLite
from models.moderation import ModerationResultUpdate, AsyncTaskStatusRequest
from clients.kafka import ModerationProducer
from errors import AdvertisementNotFoundError 

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ModerationWorker:
    def __init__(self):
        self._bootstrap = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
        self.consumer = None
        
        self.ml_service = AdvertisementMLService()
        self.moderation_repo = ModerationRepository()
        self.dlq_producer = ModerationProducer()
        
        self.MAX_RETRIES = 3
        self.RETRY_DELAY = 5 

    async def start(self):
        self.ml_service._load_model()
        logger.info("ML Model loaded")

        self.consumer = AIOKafkaConsumer(
            'moderation',
            bootstrap_servers=self._bootstrap,
            group_id='moderation_worker_group',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=False 
        )
        await self.consumer.start()
        await self.dlq_producer.start()
        logger.info("Kafka Consumer and DLQ Producer started")

    async def stop(self):
        if self.consumer:
            await self.consumer.stop()
        if self.dlq_producer:
            await self.dlq_producer.stop()
        logger.info("Worker stopped")
        
    async def process_dlq(self, data, error_msg, attempt_count):
        task_id = data.get('moderation_id')
        logger.error(f"Moving task {task_id} to DLQ. Error: {error_msg}")

        try:
            error_dto = ModerationResultUpdate(
                status="failed",
                error_message=error_msg
            )
            try:
                await self.moderation_repo.update_result(
                    dto=AsyncTaskStatusRequest(task_id=task_id), 
                    update_data=error_dto
                )
            except Exception as db_err:
                logger.error(f"Failed to update DB status for DLQ task {task_id}: {db_err}")
            
            dlq_message = {
                "original_message": data,
                "error": error_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "retry_count": attempt_count
            }
            await self.dlq_producer.send_message('moderation_dlq', dlq_message)
            
        except Exception as e:
            logger.critical(f"FAILED TO SEND TO DLQ task {task_id}: {e}")

    async def consume(self):
        await self.start()
        try:
            logger.info("Waiting for messages...")
            async for msg in self.consumer:
                data = msg.value
                task_id = data.get('moderation_id')
                item_id = data.get('item_id')

                if not item_id or not task_id:
                    logger.error(f"Invalid message format: {data}")
                    await self.consumer.commit()
                    continue

                logger.info(f"Processing task_id={task_id}")
                success = False

                for attempt in range(1, self.MAX_RETRIES + 1):
                    try:
                        adv_lite = AdvertisementLite(item_id=item_id)
                        is_violation, proba = await self.ml_service.simple_predict(adv_lite)
                        
                        update_dto = ModerationResultUpdate(
                            status="completed",
                            is_violation=is_violation,
                            probability=proba
                        )
                        
                        await self.moderation_repo.update_result(
                            dto=AsyncTaskStatusRequest(task_id=task_id), 
                            update_data=update_dto
                        )
                        
                        logger.info(f"Task {task_id} completed on attempt {attempt}")
                        success = True
                        break 

                    except AdvertisementNotFoundError as e:
                        logger.error(f"Logical error (no retry): {e}")
                        await self.process_dlq(data, str(e), attempt)
                        success = True
                        break

                    except Exception as e:
                        logger.warning(f"Attempt {attempt}/{self.MAX_RETRIES} failed for task {task_id}: {e}")
                        
                        if attempt < self.MAX_RETRIES:
                            logger.info(f"Retrying in {self.RETRY_DELAY} seconds...")
                            await asyncio.sleep(self.RETRY_DELAY)
                        else:
                            await self.process_dlq(data, str(e), attempt)
                            success = True

                if success:
                    await self.consumer.commit()
                else:
                    logger.critical(f"Task {task_id} failed catastrophically. Committing to skip.")
                    await self.consumer.commit()

        finally:
            await self.stop()

if __name__ == "__main__":
    worker = ModerationWorker()
    try:
        asyncio.run(worker.consume())
    except KeyboardInterrupt:
        logger.info("Worker stopped manually")
