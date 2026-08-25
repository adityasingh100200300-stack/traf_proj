import logging
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)

class RedisManager:
    def __init__(self):
        self.client = None

    async def connect(self):
        try:
            self.client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            await self.client.ping()
        except Exception as e:
            logger.warning(f"Could not connect to Redis at {settings.REDIS_URL}: {e}")
            self.client = None

    async def disconnect(self):
        if self.client:
            try:
                await self.client.close()
            except Exception:
                pass
            self.client = None

redis_manager = RedisManager()