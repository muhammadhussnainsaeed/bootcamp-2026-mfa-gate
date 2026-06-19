import pytest
from httpx import AsyncClient

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio

async def test_register_user(client: AsyncClient):
    """Tests if a user can successfully register and get a TOTP secret back."""
    response = await client.post("/auth/register", params={
        "username": "test_user",
        "phone": "+1234567890"
    })
    
    assert response.status_code == 201
    data = response.json()
    assert data["message"] == "User created"
    assert "user_id" in data

async def test_login_and_verify_happy_path(client: AsyncClient, redis_client):
    """Tests the full MFA SMS flow: Register -> Login -> Fetch PIN -> Verify."""
    # 1. Register
    await client.post("/auth/register", params={"username": "alice", "phone": "+1999999999"})
    
    # 2. Trigger Login
    login_res = await client.post("/auth/login", json={"username": "alice"})
    assert login_res.status_code == 200
    user_id = login_res.json()["user_id"]
    
    # 3. Sneak into Redis to grab the generated PIN (simulating checking SMS)
    pin = await redis_client.get(f"pin:{user_id}")
    assert pin is not None
    
    # 4. Verify the correct PIN
    verify_res = await client.post("/auth/verify", params={"user_id": user_id, "token": pin})
    assert verify_res.status_code == 200
    assert verify_res.json()["message"] == "Authentication via sms successful"

async def test_wrong_pin_and_max_attempts(client: AsyncClient, redis_client):
    """Demonstrates failure mode: Entering the wrong PIN and hitting the 3-attempt cap."""
    await client.post("/auth/register", params={"username": "bob", "phone": "+1888888888"})
    login_res = await client.post("/auth/login", json={"username": "bob"})
    user_id = login_res.json()["user_id"]
    
    # Attempt 1: Wrong
    res1 = await client.post("/auth/verify", params={"user_id": user_id, "token": "000000"})
    assert res1.status_code == 400
    assert "Remaining attempts: 2" in res1.json()["detail"]
    
    # Attempt 2: Wrong
    res2 = await client.post("/auth/verify", params={"user_id": user_id, "token": "000000"})
    assert res2.status_code == 400
    
    # Attempt 3: Wrong (Lockout)
    res3 = await client.post("/auth/verify", params={"user_id": user_id, "token": "000000"})
    assert res3.status_code == 400
    assert "Max attempts reached" in res3.json()["detail"]

async def test_expired_pin(client: AsyncClient, redis_client):
    """Demonstrates failure mode: The 5-minute expiry window lapses."""
    await client.post("/auth/register", params={"username": "charlie", "phone": "+1777777777"})
    login_res = await client.post("/auth/login", json={"username": "charlie"})
    user_id = login_res.json()["user_id"]
    
    pin = await redis_client.get(f"pin:{user_id}")
    
    # Simulate time passing by manually deleting the key from the fake Redis instance
    await redis_client.delete(f"pin:{user_id}")
    
    verify_res = await client.post("/auth/verify", params={"user_id": user_id, "token": pin})
    assert verify_res.status_code == 400
    assert "PIN expired" in verify_res.json()["detail"]