"""
PSEUDOCODE:
1. Public (no-auth) routes. Slice A scope: /, /health. Slice B adds /sign-in and callback.
2. /health returns {"status":"ok"} — liveness probe for Docker HEALTHCHECK and Traefik.
3. Every public route has a JSON twin under /api/v1/ where applicable.

IMPLEMENTATION: Slice A.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()
api_router = APIRouter(prefix="/api/v1")


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="landing.html",
        context={"page_title": "ds-meal", "user": None},
    )


@router.get("/health")
async def health_html():
    return JSONResponse({"status": "ok", "service": "ds-meal"})


@api_router.get("/health")
async def health_json():
    return JSONResponse({"status": "ok", "service": "ds-meal"})


# Phase 2 Graduation: Slice B fills /sign-in, /sign-in/callback, /sign-out (Clerk).
