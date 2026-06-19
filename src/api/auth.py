from fastapi import APIRouter, Depends, HTTPException, status
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.services import totp_service
from src.core.database import get_session
from src.core.redis import get_redis_client
from src.services import auth_service
from src.models.user import User
from src.schemas.auth_schemas import LoginRequest
from typing import Literal

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(username: str, phone: str, db: AsyncSession = Depends(get_session)):
    user = await auth_service.create_new_user(db, username, phone)
    return {"message": "User created", "user_id": user.id}

@router.post("/login")
async def login(
        request: LoginRequest,
        db: AsyncSession = Depends(get_session),
        redis_client: redis.Redis = Depends(get_redis_client)
):
    # 1. Query Postgres for the username
    stmt = select(User).where(User.username == request.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # 2. Handle missing users (Security note below)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # 3. Generate and store the PIN in Redis using the internal user.id
    pin = await auth_service.generate_and_store_pin(redis_client, user.id)

    # 4. Dispatch the mock SMS using the user's actual registered phone number
    print(f"📡 [MOCK SMS OUTBOUND] To {user.phone_number} (User #{user.id}) -> Security Code: {pin}")

    # We return the user_id here so the frontend knows which ID to send to the /verify endpoint next
    return {
        "message": "Verification token sent to registered device",
        "user_id": user.id
    }

@router.post("/verify")
async def verify(user_id: int, token: str, token_type: Literal["sms", "totp"] = "sms",
        db: AsyncSession = Depends(get_session) , redis_client: redis.Redis = Depends(get_redis_client)):
    if token_type == "sms":
        # Check Redis
        is_valid, message = await auth_service.verify_pin(redis_client, user_id, token)
        if not is_valid:
            raise HTTPException(status_code=400, detail= message)

    elif token_type == "totp":
        # Check Database secret
        user = await db.execute(select(User).where(User.id == user_id))
        user_obj = user.scalar_one_or_none()

        if not user_obj or not totp_service.verify_totp_code(user_obj.totp_secret, token):
            raise HTTPException(status_code=400, detail="Invalid TOTP code")

    return {"message": f"Authentication via {token_type} successful"}

@router.get("/qr-code/{username}")
async def get_qr(username: str, secret: str):
    uri = totp_service.get_totp_uri(username, secret)
    qr_base64 = totp_service.generate_qr_code_base64(uri)
    return {"qr_image": qr_base64}


