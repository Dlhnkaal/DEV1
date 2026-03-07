import json
import logging
import os
from aiokafka import AIOKafkaProducer
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class ModerationProducer:
    def __init__(self):
        self._bootstrap = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
        self._producer = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(bootstrap_servers=self._bootstrap)
        await self._producer.start()

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()

    async def send_moderation_request(self, moderation_id: int, item_id: int) -> None:
        message = {
            'moderation_id': moderation_id, 
            'item_id': item_id, 
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        await self.send_message('moderation', message)

    async def send_message(self, topic: str, message: dict) -> None:
        if not self._producer:
            await self.start()
        
        try:
            data = json.dumps(message).encode("utf-8")
            await self._producer.send_and_wait(topic, data)
        except Exception as e:
            logger.error(f"Kafka send error to topic {topic}: {e}")
            raise e
