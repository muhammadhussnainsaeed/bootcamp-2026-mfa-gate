from contextlib import asynccontextmanager
from fastapi import FastAPI
from temporalio.client import Client
from src.api import auth
from src.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [STARTUP] Booting server and configuring database schemas...")
    await init_db()
    try:
        app.state.temporal_client = await Client.connect("localhost:7233")
    except Exception as e:
        print(f"❌ [STARTUP] Failed to connect to Temporal: {e}")
        raise
    yield
    print("🛑 [SHUTDOWN] Cleaning application network pools cleanly...")


app = FastAPI(title="Bootcamp 2026: MFA Gate", lifespan=lifespan)
app.include_router(auth.router)