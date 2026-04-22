"""
PSEUDOCODE:
1. Gated calendar route — month-grid view of deliveries for the signed-in facility.
2. GET /calendar?year=Y&month=M — defaults to today.
3. Calls services.calendar_view.build_month_grid(year, month, facility_id).
4. Jinja renders month.html with weeks x days x orders cells. Each cell shows a status-colored dot per order.
5. /api/v1/calendar JSON twin returns the same grid as structured JSON.
6. Prev/next links via query string; today's cell highlighted.

IMPLEMENTATION: Phase 4.

Contract: docs/workflows/DOMAIN-WORKFLOW.md §7.
"""

from datetime import date
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

# from app.auth.dependencies import require_login
# from app.services.calendar_view import build_month_grid

router = APIRouter()
api_router = APIRouter(prefix="/api/v1")


# PSEUDO:
# - user = require_login(request)
# - y = year or today.year; m = month or today.month
# - grid = build_month_grid(y, m, user.facility_id)
# - render calendar/month.html
@router.get("/calendar", response_class=HTMLResponse)
async def calendar_month(
    request: Request,
    year: int | None = Query(None, ge=2020, le=2050),
    month: int | None = Query(None, ge=1, le=12),
):
    raise NotImplementedError


@api_router.get("/calendar")
async def calendar_month_json(
    year: int | None = Query(None),
    month: int | None = Query(None),
):
    raise NotImplementedError


# Phase 2 Graduation:
#   - Replace Jinja with FullCalendar.js SPA consuming /api/v1/calendar. Zero backend change.
