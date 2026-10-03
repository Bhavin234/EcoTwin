"""
Demo API route (docs/API.md; docs Milestone 5, requirement #21).

Exposes `app.services.demo_service.run_demo` over HTTP — this is the
endpoint a future frontend "Run EcoTwin Demo" button will call
(Milestone 6+); no UI is built here.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.intervention import DemoResultOut, ResetDemoRequest, ResetDemoResponse, RunDemoRequest
from app.services.demo_service import reset_demo_location, run_demo

router = APIRouter(tags=["demo"])


@router.post("/demo/run", response_model=DemoResultOut)
def run_demo_route(request: RunDemoRequest = Body(default=RunDemoRequest()), db: Session = Depends(get_db)):
    result = run_demo(db, scenario=request.scenario, location_name=request.location_name)
    return DemoResultOut(**result.__dict__)


@router.post("/demo/reset", response_model=ResetDemoResponse)
def reset_demo_route(request: ResetDemoRequest = Body(default=ResetDemoRequest()), db: Session = Depends(get_db)):
    """
    Fully clears the named demo location so the next /demo/run starts
    genuinely fresh (docs Milestone 7, requirement #16-17) — scoped to
    that one location only, never other data.
    """
    was_reset = reset_demo_location(db, location_name=request.location_name)
    return ResetDemoResponse(reset=was_reset, location_name=request.location_name)
