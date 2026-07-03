import secrets
import pyotp
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.user import User
import redis.exceptions


async def create_new_user(db: AsyncSession, username: str, phone: str) -> User:
    secret = pyotp.random_base32()
    user = User(username=username, phone_number=phone, totp_secret=secret)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def generate_and_store_pin(redis_client: redis.Redis, user_id: int) -> tuple[bool, str]:
    # Generate cryptographically secure 6-digit PIN
    pin = f"{secrets.randbelow(900000) + 100000}"

    try:
        # Store PIN (5 min TTL) and reset attempt counter simultaneously
        async with redis_client.pipeline(transaction=True) as pipe:
            await pipe.setex(f"pin:{user_id}", 300, pin)
            await pipe.setex(f"attempts:{user_id}", 300, "0")
            await pipe.execute()
    except redis.exceptions.RedisError:
        return False, "Service temporarily unavailable. Please try again shortly."

    print(f"#####     PIN for userID({user_id}): {pin}     #####")
    return True, pin

async def verify_pin(redis_client: redis.Redis, user_id: int, input_pin: str) -> tuple[bool, str]:
    pin_key = f"pin:{user_id}"
    attempt_key = f"attempts:{user_id}"

    try:
        stored_pin = await redis_client.get(pin_key)
    except redis.exceptions.RedisError:
        return False, "Service temporarily unavailable. Please try again shortly."

    if not stored_pin:
        return False, "PIN expired or never requested."

    try:
        attempts = await redis_client.incr(attempt_key)
    except redis.exceptions.RedisError:
        return False, "Service temporarily unavailable. Please try again shortly."

    if attempts > 3:
        return False, "Max attempts reached. Request a new PIN."

    if stored_pin == input_pin:
        try:
            await redis_client.delete(pin_key, attempt_key)
        except redis.exceptions.RedisError:
            pass  # best-effort cleanup; success already achieved
        return True, "Success"

    remaining = 3 - attempts
    if remaining <= 0:
        return False, "Max attempts reached. Request a new PIN."
    return False, f"Invalid PIN. Remaining attempts: {remaining}"
