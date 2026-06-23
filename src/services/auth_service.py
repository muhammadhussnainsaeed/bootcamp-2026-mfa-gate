import secrets
import pyotp
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.user import User
import logging


async def create_new_user(db: AsyncSession, username: str, phone: str) -> User:
    secret = pyotp.random_base32()
    user = User(username=username, phone_number=phone, totp_secret=secret)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def generate_and_store_pin(redis_client: redis.Redis, user_id: int) -> str:
    # Generate cryptographically secure 6-digit PIN
    pin = f"{secrets.randbelow(900000) + 100000}"

    print(f"--PIN for {user_id}: {pin}")
    # Store PIN (5 mins Time to Live) and reset attempt counter simultaneously
    async with redis_client.pipeline(transaction=True) as pipe:
        await pipe.setex(f"pin:{user_id}", 300, pin)
        await pipe.setex(f"attempts:{user_id}", 300, "0")
        await pipe.execute()

    return pin


async def verify_pin(redis_client: redis.Redis, user_id: int, input_pin: str) -> tuple[bool, str]:
    pin_key = f"pin:{user_id}"
    attempt_key = f"attempts:{user_id}"

    # Check-on-read lookup
    stored_pin = await redis_client.get(pin_key)
    if not stored_pin:
        return False, "PIN expired or never requested."

    attempts = int(await redis_client.get(attempt_key) or 0)
    if attempts >= 3:
        return False, "Max attempts reached. Request a new PIN."

    if stored_pin == input_pin:
        # Success: Clean up keys immediately
        await redis_client.delete(pin_key, attempt_key)
        return True, "Success"

    # Mis-match: Increment attempts atomically
    new_attempts = await redis_client.incr(attempt_key)
    if new_attempts >= 3:
        return False, "Max attempts reached. Request a new PIN."
    return False, f"Invalid PIN. Remaining attempts: {3 - new_attempts}"
