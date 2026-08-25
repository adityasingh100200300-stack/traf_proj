import json
import logging
from typing import Optional, Any
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)

class RedisManager:
    def __init__(self):
        self.client: Optional[redis.Redis] = None

    async def connect(self):
        try:
            self.client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            await self.client.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.warning(f"Could not connect to Redis at {settings.REDIS_URL}: {e}")
            self.client = None

    async def disconnect(self):
        if self.client:
            await self.client.close()
            logger.info("Disconnected from Redis")

    async def publish_event(self, channel: str, message: dict) -> bool:
        if self.client:
            try:
                await self.client.publish(channel, json.dumps(message))
                return True
            except Exception as e:
                logger.error(f"Failed to publish to Redis channel {channel}: {e}")
        return False

    async def set_state(self, key: str, value: Any, expire: int = 3600) -> bool:
        if self.client:
            try:
                await self.client.set(key, json.dumps(value), ex=expire)
                return True
            except Exception as e:
                logger.error(f"Failed to set Redis key {key}: {e}")
        return False

    async def get_state(self, key: str) -> Optional[Any]:
        if self.client:
            try:
                data = await self.client.get(key)
                return json.loads(data) if data else None
            except Exception as e:
                logger.error(f"Failed to get Redis key {key}: {e}")
        return None

redis_manager = RedisManager()