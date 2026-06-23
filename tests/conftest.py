import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
import fakeredis.aioredis

# Ensure app import doesn't fail when DATABASE_URL is unset in CI/local test runs.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
# Import your FastAPI app and dependencies
from src.main import app
from src.core.database import get_session
from src.core.redis import get_redis_client
from src.models.user import User  # Needed so SQLModel knows about your tables

# 1. Setup an in-memory SQLite database for blazing-fast isolated tests
# We use aiosqlite as the async driver for SQLite
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import StaticPool
...
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=False,
    future=True,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)

@pytest_asyncio.fixture
async def db_session():
    """Creates a fresh in-memory database for every single test."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

@pytest_asyncio.fixture
async def redis_client():
    """Provides an isolated, in-memory fake Redis instance."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()

@pytest_asyncio.fixture
async def client(db_session, redis_client):
    """
    Overrides FastAPI's dependencies so endpoints hit the test DB and test Redis 
    instead of production systems, then provides an async HTTP client.
    """
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_redis_client] = lambda: redis_client
    
    # ASGITransport is the modern way to test FastAPI with async HTTPX
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
        
    app.dependency_overrides.clear()
