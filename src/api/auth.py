import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status, Header
import redis.asyncio as redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from temporalio.client import Client, WorkflowHandle
from temporalio.common import WorkflowIDReusePolicy
from src.temporal.workflows import MFAEscalationWatcher
from src.services import totp_service
from src.core.database import get_session
from src.core.redis import get_redis_client
from src.services import auth_service
from src.models.user import User
from src.schemas.auth_schemas import LoginRequest
from src.temporal.client import get_temporal_client, get_workflow_handle, get_workflow_reason

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(username: str, phone: str, db: AsyncSession = Depends(get_session)):
    try:
        user = await auth_service.create_new_user(db, username, phone)
        return {"message": "User created", "user_id": user.id}
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or phone number already registered"
        )

@router.post("/login")
async def login(
        request: LoginRequest,
        db: AsyncSession = Depends(get_session),
        redis_client: redis.Redis = Depends(get_redis_client),
        temporal_client: Client = Depends(get_temporal_client),
):
    # 1. Fetch User
    """
        Send a verification token for a user's login attempt.
        
        Parameters:
        	request (LoginRequest): Login credentials containing the username.
        
        Returns:
        	dict: A response with the user ID and a message confirming that a verification token was sent.
        """
        stmt = select(User).where(User.username == request.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. Check if they are locked out (Temporal Escalation or 3-Strikes)
    locked_reason = await redis_client.get(f"locked:{user.id}")
    if locked_reason:
        ttl_seconds = await redis_client.ttl(f"locked:{user.id}")
        raise HTTPException(
            status_code=403,
            detail={
                "message": f"Account is locked ({locked_reason}). Contact support.",
                "reason": locked_reason,
                "seconds_remaining": ttl_seconds if ttl_seconds > 0 else 0,
            }
        )

    # 3. NEW: The Cooldown Check (Prevents SMS Bombing & Simultaneous calls)
    cooldown = await redis_client.get(f"cooldown:{user.id}")
    if cooldown:
        ttl = await redis_client.ttl(f"cooldown:{user.id}")
        raise HTTPException(
            status_code=429, # 429 Too Many Requests
            detail=f"Please wait {ttl} seconds before requesting a new PIN."
        )

    # 4. Generate and store the PIN
    ok, result_msg = await auth_service.generate_and_store_pin(redis_client, user.id)
    if not ok:
        raise HTTPException(status_code=503, detail=result_msg)

    # 5. NEW: Set the Cooldown Timer (60 seconds)
    # This ensures they cannot hit this API again for exactly 1 minute.
    await redis_client.setex(f"cooldown:{user.id}", 60, "1")

    # 6. Start the Temporal Watcher
    workflow_id = f"mfa-watcher-{user.id}"
    await temporal_client.start_workflow(
        MFAEscalationWatcher.run,
        args=[user.id],
        id=workflow_id,
        task_queue="mfa-watcher-queue",
        id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
    )

    return {
        "message": "Verification token sent to registered device",
        "user_id": user.id
    }


@router.post("/verify")
async def verify(
        user_id: int,
        token: str,
        token_type: Literal["sms", "totp"] = "sms",
        db: AsyncSession = Depends(get_session),
        redis_client: redis.Redis = Depends(get_redis_client),
        temporal_client: Client = Depends(get_temporal_client),
):
    """
        Verify an SMS or TOTP authentication code for a user.
        
        Parameters:
        	user_id (int): The user to authenticate.
        	token (str): The verification code to check.
        	token_type (Literal["sms", "totp"]): The code type to verify.
        
        Returns:
        	dict: A success response with the authentication message and workflow status, or a warning response if workflow confirmation fails.
        """
        handle = get_workflow_handle(temporal_client, user_id)

    if token_type == "sms":
        is_valid, message = await auth_service.verify_pin(redis_client, user_id, token)
        if not is_valid:
            if "Max attempts reached" in message:
                try:
                    await handle.signal(MFAEscalationWatcher.mark_as_failed)
                except Exception as e:
                    print(f"Warning: Could not signal failure to Temporal. {e}")

                # Immediate lock — don't wait on the activity round trip.
                await redis_client.setex(f"locked:{user_id}", 600, "max_attempts")
                raise HTTPException(status_code=400, detail=message)

            raise HTTPException(status_code=400, detail=message)

    elif token_type == "totp":
        user = await db.execute(select(User).where(User.id == user_id))
        user_obj = user.scalar_one_or_none()

        if not user_obj or not totp_service.verify_totp_code(user_obj.totp_secret, token):
            raise HTTPException(status_code=400, detail="Invalid TOTP code")

    try:
        await handle.signal(MFAEscalationWatcher.mark_as_verified)
    except Exception as e:
        print(f"CRITICAL: Could not signal Temporal workflow for user {user_id}. {e}")
        return {
            "message": f"Authentication via {token_type} accepted, but could not confirm "
                       f"workflow cleanup — treat as unverified until confirmed.",
            "status": "warning",
        }

    reason = await get_workflow_reason(handle)
    return {
        "message": f"Authentication via {token_type} successful",
        "workflow_status": reason,  # e.g. "verified"
    }


@router.get("/qr-code/{username}")
async def get_qr(username: str, db: AsyncSession = Depends(get_session)):
    """
    Generate a QR code image for a user's TOTP enrollment.
    
    Raises:
    	HTTPException: If the user is not found or TOTP is not configured.
    
    Returns:
    	dict: A mapping containing the QR code image as a base64-encoded string.
    """
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user or not user.totp_secret:
        raise HTTPException(status_code=404, detail="User not found or TOTP not configured")
    uri = totp_service.get_totp_uri(username, user.totp_secret)
    qr_base64 = totp_service.generate_qr_code_base64(uri)
    return {"qr_image": qr_base64}

@router.post("/unlock/{user_id}")
async def unlock_account(
        user_id: int,
        db: AsyncSession = Depends(get_session),
        redis_client: redis.Redis = Depends(get_redis_client),
        _: None = Depends(auth_service.verify_internal_api_key),
):
    """
        Unlock a user's authentication state.
        
        Parameters:
        	user_id (int): The user identifier.
        
        Returns:
        	dict: A message indicating whether the user was unlocked or was not locked.
        """
        result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    was_locked = await redis_client.get(f"locked:{user_id}")

    await redis_client.delete(
        f"locked:{user_id}",
        f"pin:{user_id}",
        f"attempts:{user_id}",
    )

    if not was_locked:
        return {"message": f"User {user_id} was not locked. No action needed."}

    return {"message": f"User {user_id} has been unlocked and can log in again."}