import asyncio
import os

from dotenv import load_dotenv
import redis.asyncio as redis
from temporalio.client import Client
from temporalio.worker import Worker
from src.temporal.activities import lock_account_activity, init_activity_dependencies
from src.temporal.workflows import MFAEscalationWatcher
from src.core.redis import REDIS_URL

load_dotenv()

async def main():

    TEMPORAL_HOST = os.getenv("localhost:7233")

    client = await Client.connect(TEMPORAL_HOST)

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