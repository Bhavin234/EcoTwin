"""
Shared error handling.

Per docs/API.md: "Errors: {error: {code, message}} — never a raw stack
trace to the frontend." This module wires that convention up for every
error path FastAPI can produce, not just the ones individual routes
happen to catch.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("ecotwin")


def _error_body(code: str, message: str, details: list | None = None) -> dict:
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        # Routes may already pass a well-formed {code, message, details}
        # dict as `detail` (see app/api/telemetry.py); normalize either way.
        if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
            body = _error_body(exc.detail["code"], exc.detail["message"], exc.detail.get("details"))
        else:
            body = _error_body(code=f"http_{exc.status_code}", message=str(exc.detail))
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        details = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        return JSONResponse(
            status_code=422,
            content=_error_body("request_validation_failed", "The request did not match the expected format.", details),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Never leak a raw stack trace to the client (docs/API.md,
        # docs/RELIABILITY_AND_TRUST.md) — log it server-side instead.
        logger.exception("Unhandled exception while processing %s %s", request.method, request.url)
        return JSONResponse(
            status_code=500,
            content=_error_body("internal_error", "An unexpected error occurred. Please try again."),
        )
