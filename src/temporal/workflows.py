import asyncio
from datetime import timedelta
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.temporal.activities import lock_account_activity


@workflow.defn
class MFAEscalationWatcher:
    def __init__(self) -> None:
        self.is_verified = False
        self.is_failed = False

    @workflow.signal
    def mark_as_verified(self) -> None:
        self.is_verified = True

    @workflow.signal
    def mark_as_failed(self) -> None:
        self.is_failed = True

    @workflow.run
    async def run(self, user_id: int) -> str:
        try:
            await workflow.wait_condition(
                lambda: self.is_verified or self.is_failed,
                timeout=timedelta(minutes=5),
            )
        except asyncio.TimeoutError:
            await workflow.execute_activity(
                lock_account_activity,
                args=[user_id, "timeout"],
                start_to_close_timeout=timedelta(seconds=10),
            )
            return "locked:timeout"

        if self.is_verified:
            return "verified"

        await workflow.execute_activity(
            lock_account_activity,
            args=[user_id, "max_attempts"],
            start_to_close_timeout=timedelta(seconds=10),
        )
        return "locked:max_attempts"