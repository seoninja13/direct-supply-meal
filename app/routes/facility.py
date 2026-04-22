"""
Facility dashboard route — the landing destination after sign-in.

Slice B ships a placeholder dashboard. Slice C fills in active-orders summary +
quick-reorder tiles.

Contract: DOMAIN-WORKFLOW.md §4 J2.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, require_login
from app.db.database import get_session
from app.models.facility import Facility

router = APIRouter()
api_router = APIRouter(prefix="/api/v1")


async def _load_facility(session: AsyncSession, facility_id: int) -> Facility | None:
    return await session.get(Facility, facility_id)


@router.get("/facility/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: Annotated[CurrentUser, Depends(require_login)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    facility = await _load_facility(session, user.facility_id)
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="facility/dashboard.html",
        context={
            "page_title": "Dashboard — ds-meal",
            "user": user,
            "facility": facility,
            "active_orders": [],  # Slice C fills this in.
            "next_delivery": None,
        },
    )


@api_router.get("/facility/me")
async def facility_me_json(
    user: Annotated[CurrentUser, Depends(require_login)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    facility = await _load_facility(session, user.facility_id)
    return JSONResponse(
        {
            "user": {
                "id": user.user_id,
                "email": user.email,
                "facility_id": user.facility_id,
            },
            "facility": (
                {
                    "id": facility.id,
                    "name": facility.name,
                    "type": facility.type.value if facility else None,
                    "bed_count": facility.bed_count,
                }
                if facility
                else None
            ),
        }
    )


# Phase 2 Graduation: Slice C populates active_orders via
# app.services.orders.list_orders_for_facility. Slice H adds recent_templates
# (most-ordered recipes in last 30 days).
