"""
Gated calendar route — month-grid view of deliveries for the signed-in facility.

Contract: DOMAIN-WORKFLOW.md §7.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, require_login
from app.db.database import get_session
from app.services.calendar_view import build_month_grid

router = APIRouter()
api_router = APIRouter(prefix="/api/v1")

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


@router.get("/calendar", response_class=HTMLResponse)
async def calendar_month(
    request: Request,
    user: Annotated[CurrentUser, Depends(require_login)],
    session: Annotated[AsyncSession, Depends(get_session)],
    year: int | None = Query(None, ge=2020, le=2050),
    month: int | None = Query(None, ge=1, le=12),
):
    grid = await build_month_grid(session, year, month, user.facility_id)
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="calendar/month.html",
        context={
            "page_title": "Calendar — ds-meal",
            "user": user,
            "grid": grid,
            "month_name": MONTH_NAMES[grid["month"] - 1],
        },
    )


@api_router.get("/calendar")
async def calendar_month_json(
    user: Annotated[CurrentUser, Depends(require_login)],
    session: Annotated[AsyncSession, Depends(get_session)],
    year: int | None = Query(None),
    month: int | None = Query(None),
):
    grid = await build_month_grid(session, year, month, user.facility_id)
    # Dates -> ISO strings for JSON serialization.
    weeks_json: list[list[dict]] = []
    for week in grid["weeks"]:
        row: list[dict] = []
        for cell in week:
            row.append(
                {
                    "date": cell["date"].isoformat() if cell["date"] else None,
                    "day_of_month": cell["day_of_month"],
                    "in_month": cell["in_month"],
                    "is_today": cell["is_today"],
                    "orders": cell["orders"],
                }
            )
        weeks_json.append(row)
    return JSONResponse(
        {
            "year": grid["year"],
            "month": grid["month"],
            "weeks": weeks_json,
            "prev": grid["prev"],
            "next": grid["next"],
            "today": grid["today"].isoformat(),
        }
    )


# Phase 2 Graduation:
#   - Replace Jinja with FullCalendar.js SPA consuming /api/v1/calendar. Zero backend change.
