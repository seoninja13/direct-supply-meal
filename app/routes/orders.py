"""
Gated order routes — history (/orders), detail (/orders/{id}), plus JSON twins.

`/orders/new` (NL Ordering agent) is a Slice D surface and returns 501 here.

Contract: DOMAIN-WORKFLOW.md §4 J5 + §3 state machine.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, require_facility_access, require_login
from app.db.database import get_session
from app.services.orders import (
    OrderNotFound,
    get_order_with_timeline,
    list_orders_for_facility,
    progress_fraction,
)

router = APIRouter()
api_router = APIRouter(prefix="/api/v1")

_ALLOWED_STATUSES = {
    "pending",
    "confirmed",
    "in_preparation",
    "out_for_delivery",
    "delivered",
    "cancelled",
}


def _validate_status(raw: str | None) -> str | None:
    if raw is None or raw == "":
        return None
    if raw not in _ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"invalid status: {raw}")
    return raw


@router.get("/orders", response_class=HTMLResponse)
async def list_orders(
    request: Request,
    user: Annotated[CurrentUser, Depends(require_login)],
    session: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
):
    status_filter = _validate_status(status)
    page_data = await list_orders_for_facility(
        session,
        facility_id=user.facility_id,
        status_filter=status_filter,
        page=page,
        page_size=25,
    )
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="orders/list.html",
        context={
            "page_title": "Orders — ds-meal",
            "user": user,
            "orders": page_data["items"],
            "page": page_data["page"],
            "total_pages": page_data["total_pages"],
            "total": page_data["total"],
            "status_filter": status_filter,
            "allowed_statuses": sorted(_ALLOWED_STATUSES),
        },
    )


@api_router.get("/orders")
async def list_orders_json(
    user: Annotated[CurrentUser, Depends(require_login)],
    session: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
):
    status_filter = _validate_status(status)
    page_data = await list_orders_for_facility(
        session,
        facility_id=user.facility_id,
        status_filter=status_filter,
        page=page,
        page_size=25,
    )
    return JSONResponse(page_data)


# --- Slice D surfaces — declared BEFORE /orders/{order_id} so "new" isn't
# parsed as an int path param. Return 501 for now; Slice D fills in the body. ---

@router.get("/orders/new", response_class=HTMLResponse)
async def new_order_form(
    request: Request,
    user: Annotated[CurrentUser, Depends(require_login)],
    trace_id: str | None = Query(None),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="NL Ordering agent ships with Slice D",
    )


@router.post("/orders/new", response_class=HTMLResponse)
async def submit_order(
    request: Request,
    user: Annotated[CurrentUser, Depends(require_login)],
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="NL Ordering agent ships with Slice D",
    )


@api_router.post("/orders")
async def create_order_json(
    request: Request,
    user: Annotated[CurrentUser, Depends(require_login)],
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="NL Ordering agent ships with Slice D",
    )


@router.get("/orders/{order_id}", response_class=HTMLResponse)
async def order_detail(
    request: Request,
    order_id: int,
    user: Annotated[CurrentUser, Depends(require_login)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    try:
        detail = await get_order_with_timeline(session, order_id)
    except OrderNotFound as exc:
        raise HTTPException(status_code=404, detail="order_not_found") from exc

    require_facility_access(detail["order"]["facility_id"], user)

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="orders/detail.html",
        context={
            "page_title": f"Order #{order_id} — ds-meal",
            "user": user,
            "order": detail["order"],
            "lines": detail["lines"],
            "timeline": detail["timeline"],
            "progress_fraction": progress_fraction(detail["order"]["status"]),
        },
    )


@api_router.get("/orders/{order_id}")
async def order_detail_json(
    order_id: int,
    user: Annotated[CurrentUser, Depends(require_login)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    try:
        detail = await get_order_with_timeline(session, order_id)
    except OrderNotFound as exc:
        raise HTTPException(status_code=404, detail="order_not_found") from exc
    require_facility_access(detail["order"]["facility_id"], user)
    return JSONResponse(detail)


# Phase 2 Graduation:
#   - Add /orders/{id}/cancel route. Seam: services.orders.advance_order_status(id, "cancelled").
#   - Status transitions emit Inngest events. Seam: advance_order_status() body.
