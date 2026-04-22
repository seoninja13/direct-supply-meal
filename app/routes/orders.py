"""
Gated order routes — history, detail, NL ordering (Slice D), plus JSON twins.

Contract: DOMAIN-WORKFLOW.md §4 J5 + §3 state machine + §4 J4 (NL ordering).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from agents.depth_scorer import score_query
from agents.drivers import dispatch as _dispatch_mod
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


# --- NL Ordering surfaces (Slice D). `/orders/new` routes MUST be declared
# BEFORE `/orders/{order_id}` so FastAPI doesn't try to parse "new" as an int. ---

@router.get("/orders/new", response_class=HTMLResponse)
async def new_order_form(
    request: Request,
    user: Annotated[CurrentUser, Depends(require_login)],
    trace_id: str | None = Query(None),
):
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="orders/new.html",
        context={
            "page_title": "New order — ds-meal",
            "user": user,
            "text": "",
            "proposal": None,
            "trace_id": trace_id,
            "error": None,
            "options": None,
        },
    )


@router.post("/orders/new", response_class=HTMLResponse)
async def submit_order(
    request: Request,
    user: Annotated[CurrentUser, Depends(require_login)],
    text: Annotated[str, Form(...)] = "",
    trace_id: Annotated[str | None, Form()] = None,
    confirm: Annotated[str | None, Form()] = None,
):
    """Two-phase NL ordering: text → proposal card (awaiting_confirmation),
    then Confirm → redirect to /orders/{id}. Depth score logged once per route
    call (G13).
    """
    # G13: score_query runs once here (advisory; Phase 1 logs only).
    score_query(text)

    result = await _dispatch_mod.invoke_director(
        "nl_ordering",
        {
            "text": text,
            "user_id": user.user_id,
            "facility_id": user.facility_id,
            "trace_id": trace_id,
            "confirm": bool(confirm),
        },
    )

    if result["status"] == "pending" and result.get("order_id"):
        return RedirectResponse(
            url=f"/orders/{result['order_id']}",
            status_code=303,
        )

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="orders/new.html",
        context={
            "page_title": "New order — ds-meal",
            "user": user,
            "text": text,
            "proposal": result.get("proposal"),
            "trace_id": result.get("trace_id"),
            "error": result.get("error"),
            "options": result.get("options"),
            "status": result["status"],
        },
    )


@api_router.post("/orders")
async def create_order_json(
    request: Request,
    user: Annotated[CurrentUser, Depends(require_login)],
    payload: Annotated[dict | None, None] = None,
):
    """JSON twin of POST /orders/new — takes JSON `{text, trace_id?, confirm?}`
    and returns the dispatch result dict. Phase 2 surface; Phase 1 tests use it
    to verify the driver plumbing without Jinja.
    """
    body = await request.json()
    text = str(body.get("text", ""))
    score_query(text)
    result = await _dispatch_mod.invoke_director(
        "nl_ordering",
        {
            "text": text,
            "user_id": user.user_id,
            "facility_id": user.facility_id,
            "trace_id": body.get("trace_id"),
            "confirm": bool(body.get("confirm", False)),
        },
    )
    # Strip raw tool_calls detail from API response — internal-only.
    result.pop("tool_calls", None)
    return JSONResponse(result)


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
