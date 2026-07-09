from contextlib import asynccontextmanager
from fastapi import FastAPI
from temporalio.client import Client
from src.api import auth
from src.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown for the FastAPI lifespan.
    
    Parameters:
    	app (FastAPI): The application instance whose state is configured during startup.
    """
    print("🚀 [STARTUP] Booting server and configuring database schemas...")
    await init_db()
    app.state.temporal_client = await Client.connect("localhost:7233")
    yield
    print("🛑 [SHUTDOWN] Cleaning application network pools cleanly...")


app = FastAPI(title="Bootcamp 2026: MFA Gate", lifespan=lifespan)
app.include_router(auth.router)