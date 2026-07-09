import asyncio
from datetime import timedelta
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.temporal.activities import lock_account_activity


@workflow.defn
class MFAEscalationWatcher:
    def __init__(self) -> None:
        """
        Initialize the workflow state flags for verification and failure signals.
        """
        self.is_verified = False
        self.is_failed = False

    @workflow.signal
    def mark_as_verified(self) -> None:
        """
        Mark the workflow as verified.
        """
        self.is_verified = True

    @workflow.signal
    def mark_as_failed(self) -> None:
        """
        Mark the MFA attempt as failed.
        """
        self.is_failed = True

    @workflow.run
    async def run(self, user_id: int) -> str:
        """
        Wait for MFA verification or failure and lock the account when escalation is needed.
        
        Parameters:
        	user_id (int): The user account to lock if the workflow times out or receives a failure signal.
        
        Returns:
        	str: "verified" if verification is received, "locked:timeout" if the wait times out, or "locked:max_attempts" if failure is signaled.
        """
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