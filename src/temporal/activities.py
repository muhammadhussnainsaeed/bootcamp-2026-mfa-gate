from temporalio import activity
import redis.asyncio as redis


_redis_client: redis.Redis | None = None


def init_activity_dependencies(redis_client: redis.Redis) -> None:
    global _redis_client
    _redis_client = redis_client


@activity.defn
async def lock_account_activity(user_id: int, reason: str = "timeout") -> str:
    """
    Runs when a user fails MFA — either the 5-minute window expired, or they
    exhausted their PIN/TOTP attempts early.

    Now actually persists the lock, instead of just printing, so /login's
    `locked:{user_id}` check reflects reality for the timeout case too.
    """
    if _redis_client is None:
        raise RuntimeError(
            "Activity dependencies not initialized — call init_activity_dependencies() "
            "in the worker's startup before running the worker."
        )

    await _redis_client.setex(f"locked:{user_id}", 600, reason)

    print(f"\n🚨 [Temporal Activity] Locked User ID {user_id} (reason: {reason}) 🚨\n")
    return f"Account {user_id} locked due to {reason}."