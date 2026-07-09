import asyncio
from fastapi import Request
from temporalio.client import Client, WorkflowHandle


def get_temporal_client(request: Request) -> Client:
    """Reuse the single connection created in lifespan instead of
    reconnecting to Temporal on every single request."""
    return request.app.state.temporal_client


def get_workflow_handle(temporal_client: Client, user_id: int) -> WorkflowHandle:
    return temporal_client.get_workflow_handle(f"mfa-watcher-{user_id}")


async def get_workflow_reason(handle: WorkflowHandle) -> str:
    """After signalling, pull the workflow's actual completion reason
    instead of guessing at what happened."""
    try:
        # Increased to 15s to safely outlast the 10s activity timeout
        result = await asyncio.wait_for(handle.result(), timeout=15.0)
        return result
    except asyncio.TimeoutError:
        print("WARNING: Timeout waiting for workflow result. Activity may still be running.")
        return "pending_timeout"
    except Exception as e:
        print(f"WARNING: could not fetch workflow result: {e}")
        return "unknown"