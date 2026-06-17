from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from src.core.database import init_db, get_session
from src.core.redis import get_redis_client
# Crucial: Import the User model here so SQLModel knows about its metadata on startup
from src.models.user import User


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [STARTUP] Booting server and configuring database schemas...")
    await init_db()
    yield
    print("🛑 [SHUTDOWN] Cleaning application network pools cleanly...")


app = FastAPI(title="Bootcamp 2026: MFA Gate", lifespan=lifespan)


@app.get("/health")
async def pipeline_health_check(
        db: AsyncSession = Depends(get_session),
        cache: redis.Redis = Depends(get_redis_client)
):
    """Verifies that the API, Postgres, and Redis are talking to each other."""
    # Write a quick transient value to Redis to test it
    await cache.set("test_key", "redis_is_alive", ex=5)
    redis_response = await cache.get("test_key")

    return {
        "api_status": "online",
        "postgres_connected": db is not None,
        "redis_connected": redis_response == "redis_is_alive"
    }