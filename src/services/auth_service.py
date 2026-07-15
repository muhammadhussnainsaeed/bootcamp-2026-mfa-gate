import secrets
import os
import pyotp
import redis.asyncio as redis
from fastapi import HTTPException, Header
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.user import User
import logging

logger = logging.getLogger(__name__)

async def create_new_user(db: AsyncSession, username: str, phone: str) -> User:
    secret = pyotp.random_base32()
    user = User(username=username, phone_number=phone, totp_secret=secret)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def generate_and_store_pin(redis_client: redis.Redis, user_id: int) -> tuple[bool, str]:
    pin = f"{secrets.randbelow(900000) + 100000}"

    try:
        async with redis_client.pipeline(transaction=True) as pipe:
            await pipe.setex(f"pin:{user_id}", 300, pin)
            await pipe.setex(f"attempts:{user_id}", 300, "0")
            await pipe.execute()
    except RedisError:
        return False, "Service temporarily unavailable. Please try again shortly."

    # Pass the {pin} variable into the debug string!
    logger.debug(f"DEVELOPMENT ONLY - PIN for userID({user_id}): {pin}")
    logger.info(f"Successfully generated PIN for user {user_id}")
    return True, pin


async def validate_sms_pin(redis_client: redis.Redis, user_id: int, input_pin: str) -> bool:
    """Strictly checks if the PIN matches, returning True/False."""
    pin_key = f"pin:{user_id}"

    try:
        stored_pin = await redis_client.get(pin_key)
    except RedisError:
        raise HTTPException(status_code=503, detail="Cache service unavailable.")

    if not stored_pin or stored_pin != input_pin:
        return False

    # Clean up the cache immediately on success so the PIN can't be reused
    try:
        await redis_client.delete(pin_key, f"attempts:{user_id}")
    except RedisError:
        pass

    return True


async def track_verification_attempt(redis_client: redis.Redis, user_id: int, max_attempts: int = 2) -> tuple[
    bool, int]:
    """
    Increments the attempt counter for a user.
    Returns (is_locked: bool, remaining_attempts: int)
    """
    attempt_key = f"attempts:{user_id}"

    try:
        attempts = await redis_client.incr(attempt_key)
        if attempts == 1:
            # Set the counter to expire after 5 minutes to clear out old sessions
            await redis_client.expire(attempt_key, 300)
    except RedisError:
        raise HTTPException(status_code=503, detail="Cache service unavailable.")

    is_locked = attempts > max_attempts
    remaining = max(0, max_attempts - attempts)

    return is_locked, remaining


async def verify_internal_api_key(x_internal_api_key: str = Header(...)):
    expected = os.getenv("UNLOCK_KEY")
    # Use secrets.compare_digest for constant-time comparison
    if not expected or not secrets.compare_digest(x_internal_api_key, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")