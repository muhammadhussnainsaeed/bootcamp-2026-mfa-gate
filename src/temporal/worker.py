import asyncio
import redis.asyncio as redis
from temporalio.client import Client
from temporalio.worker import Worker
from src.temporal.activities import lock_account_activity, init_activity_dependencies
from src.temporal.workflows import MFAEscalationWatcher
from src.core.redis import REDIS_URL  # adjust to wherever your redis URL constant lives


async def main():
    """
    Start the Temporal worker for MFA escalation monitoring.
    
    Connects to the local Temporal server, initializes Redis-backed activity dependencies, and runs a worker on the `mfa-watcher-queue` task queue with the MFA escalation workflow and account-locking activity registered.
    """
    client = await Client.connect("localhost:7233")

    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    init_activity_dependencies(redis_client)

    worker = Worker(
        client,
        task_queue="mfa-watcher-queue",
        workflows=[MFAEscalationWatcher],
        activities=[lock_account_activity],
    )

    print("👷 Temporal Watcher Worker started. Listening for tasks...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())