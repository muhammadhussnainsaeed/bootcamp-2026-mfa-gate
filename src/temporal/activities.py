from datetime import datetime, timedelta, timezone
from temporalio import activity
import redis.asyncio as redis

# Module-level singleton, created once when the worker boots (see worker.py).
# Activities shouldn't import FastAPI's request-scoped Depends() — this is
# the standard Temporal pattern for giving an activity durable dependencies.
_redis_client: redis.Redis | None = None


def init_activity_dependencies(redis_client: redis.Redis) -> None:
    """
    Initialize the Redis client used by Temporal activities.
    
    Parameters:
    	redis_client (redis.Redis): The Redis client instance to store for later use.
    """
    global _redis_client
    _redis_client = redis_client


@activity.defn
async def lock_account_activity(user_id: int, reason: str = "timeout") -> str:
    """
    Lock a user account in Redis for a short period.
    
    Parameters:
    	user_id (int): The user to lock.
    	reason (str): The reason recorded for the lock.
    
    Returns:
    	str: A confirmation message indicating the account was locked.
    """
    if _redis_client is None:
        raise RuntimeError(
            "Activity dependencies not initialized — call init_activity_dependencies() "
            "in the worker's startup before running the worker."
        )

    await _redis_client.setex(f"locked:{user_id}", 600, reason)

    # TODO (optional, if you want it durable in Postgres too, not just Redis):
    # async with get_session_for_activity() as db:
    #     user = await db.get(User, user_id)
    #     user.is_locked = True
    #     user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
    #     await db.commit()

    print(f"\n🚨 [Temporal Activity] Locked User ID {user_id} (reason: {reason}) 🚨\n")
    return f"Account {user_id} locked due to {reason}."