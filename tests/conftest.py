import os

# 1. SET ENVIRONMENT VARIABLES FIRST
# This must happen before any local imports so database.py and main.py
# pick up the dummy URLs during their module-level initialization.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

# 2. THEN IMPORT EXTERNAL LIBRARIES
import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

# 3. FINALLY, IMPORT YOUR APP MODULES
from src.core.database import get_session
from src.core.redis import get_redis_client
from src.main import app
from src.temporal.client import get_temporal_client


class _FakeWorkflowHandle:
    def __init__(self, workflow_id: str, workflow_state: dict[str, str]):
        self.workflow_id = workflow_id
        self._workflow_state = workflow_state

    async def signal(self, signal_method):
        signal_name = getattr(signal_method, "__name__", "")
        if signal_name == "mark_as_verified":
            self._workflow_state[self.workflow_id] = "verified"
        elif signal_name == "mark_as_failed":
            self._workflow_state[self.workflow_id] = "failed"

    async def result(self):
        return self._workflow_state.get(self.workflow_id, "verified")


class _FakeTemporalClient:
    def __init__(self):
        self._workflow_state: dict[str, str] = {}

    async def start_workflow(self, *args, **kwargs):
        workflow_id = kwargs.get("id")
        if workflow_id is not None:
            self._workflow_state[workflow_id] = "pending"
        return _FakeWorkflowHandle(workflow_id, self._workflow_state)

    def get_workflow_handle(self, workflow_id: str):
        self._workflow_state.setdefault(workflow_id, "pending")
        return _FakeWorkflowHandle(workflow_id, self._workflow_state)


# Setup the dummy engine for testing
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
    temporal_client = _FakeTemporalClient()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_redis_client] = lambda: redis_client
    app.dependency_overrides[get_temporal_client] = lambda: temporal_client
    app.state.temporal_client = temporal_client

    # ASGITransport is the modern way to test FastAPI with async HTTPX
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    if hasattr(app.state, "my_mocked_dependency"):
        delattr(app.state, "my_mocked_dependency")