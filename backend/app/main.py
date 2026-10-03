"""
EcoTwin FastAPI application entrypoint.

Milestone 1 scope (see ROADMAP.md): app boots, database connects, health
endpoint responds, ORM models exist and can create their tables. The
Intelligence Core (baseline/anomaly/investigation/impact engines),
ingestion endpoints, and demo mode are built in later milestones and wired
into the `api` router package as they land — this file should not need
significant restructuring as they're added, only new `include_router`
calls.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analytics, demo, health, intervention, investigation, telemetry
from app.core.config import get_settings
from app.core.database import init_db
from app.core.errors import register_exception_handlers

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create database tables if they don't exist yet (see core/database.py)."""
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="EcoTwin: detect, investigate, recommend, and verify resource-consumption anomalies.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


register_exception_handlers(app)

app.include_router(health.router, prefix="/api")
app.include_router(telemetry.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(investigation.router, prefix="/api")
app.include_router(intervention.router, prefix="/api")
app.include_router(demo.router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {"message": "EcoTwin API is running. See /docs for the interactive API reference."}
