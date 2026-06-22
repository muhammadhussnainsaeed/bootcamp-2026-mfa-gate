import os
import redis.asyncio as redis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")

redis_pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)

async def get_redis_client() -> redis.Redis:
    """Dependency injection generator to provide an async Redis client instance."""
    client = redis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        await client.aclose()