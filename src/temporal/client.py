import asyncio
from fastapi import Request
from temporalio.client import Client, WorkflowHandle


def get_temporal_client(request: Request) -> Client:
    """Reuse the single connection created in lifespan instead of
    reconnecting to Temporal on every single request."""
    return request.app.state.temporal_client


def get_workflow_handle(temporal_client: Client, user_id: int) -> WorkflowHandle:
    """
    Get a Temporal workflow handle for a user's MFA watcher workflow.
    
    Parameters:
        temporal_client (Client): The Temporal client used to look up the workflow.
        user_id (int): The user identifier used to build the workflow ID.
    
    Returns:
        WorkflowHandle: The handle for the workflow with ID ``mfa-watcher-{user_id}``.
    """
    return temporal_client.get_workflow_handle(f"mfa-watcher-{user_id}")


async def get_workflow_reason(handle: WorkflowHandle) -> str:
    """
    Gets the workflow completion reason.
    
    Waits up to 5 seconds for the workflow result and falls back to "unknown" if the result cannot be retrieved.
    
    Returns:
        str: The workflow result, or "unknown" if it cannot be obtained.
    """
    try:
        result = await asyncio.wait_for(handle.result(), timeout=5)
        return result
    except Exception as e:
        print(f"WARNING: could not fetch workflow result: {e}")
        return "unknown"