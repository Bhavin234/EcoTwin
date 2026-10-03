"""
Health check endpoint.

Used by deployment platforms (docs/DEPLOYMENT.md) and by developers to
confirm the backend is running and can reach its database. Also reports
whether the AI Reasoning Layer is enabled, without leaking the API key
itself — useful for confirming the fallback-vs-AI path during local
testing (docs/RELIABILITY_AND_TRUST.md).
"""
from fastapi import APIRouter

from app.core.config import get_settings
from app.core.database import db_healthy

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.env,
        "database": "connected" if db_healthy() else "unreachable",
        "ai_reasoning_layer": "enabled" if settings.ai_enabled else "disabled (using deterministic fallback)",
    }
