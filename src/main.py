from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.api import auth
from src.core.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [STARTUP] Booting server and configuring database schemas...")
    await init_db()
    yield
    print("🛑 [SHUTDOWN] Cleaning application network pools cleanly...")

app = FastAPI(title="Bootcamp 2026: MFA Gate", lifespan=lifespan)

app.include_router(auth.router)
