"""
PSEUDOCODE:
1. Gated order routes — history, detail, NL ordering agent surface.
2. GET /orders — paginated history; ?status= filter, ?page= pagination.
3. GET /orders/{id} — detail with OrderLine breakdown, status timeline, progress bar.
4. GET /orders/new — NL input form (or proposal card if resuming from a trace_id).
5. POST /orders/new — invoke NL Ordering agent; return proposal for confirmation. POST with confirm=true persists.
6. /api/v1/orders, /api/v1/orders/{id} twins.
7. 403 if User.facility_id != Order.facility_id.

IMPLEMENTATION: Phase 4.

Contract: docs/workflows/DOMAIN-WORKFLOW.md §4 J4 and J5, AGENT-WORKFLOW.md §4.
"""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

# from app.auth.dependencies import require_login
# from agents.drivers.dispatch import invoke_director
# from app.services.orders import list_orders_for_facility, get_order_with_timeline

router = APIRouter()
api_router = APIRouter(prefix="/api/v1")


# PSEUDO:
# - user = require_login(request)
# - page_data = list_orders_for_facility(user.facility_id, status_filter, page, page_size=25)
# - render orders/list.html with badges
@router.get("/orders", response_class=HTMLResponse)
async def list_orders(
    request: Request,
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
):
    raise NotImplementedError


@api_router.get("/orders")
async def list_orders_json(status: str | None = Query(None), page: int = Query(1, ge=1)):
    raise NotImplementedError


# PSEUDO:
# - user = require_login(request)
# - detail = get_order_with_timeline(order_id)
# - 403 if detail.order.facility_id != user.facility_id
# - render orders/detail.html with timeline + progress_bar partial
@router.get("/orders/{order_id}", response_class=HTMLResponse)
async def order_detail(request: Request, order_id: int):
    raise NotImplementedError


@api_router.get("/orders/{order_id}")
async def order_detail_json(order_id: int):
    raise NotImplementedError


# PSEUDO: render orders/new.html with empty form + optional existing trace_id for resumption.
@router.get("/orders/new", response_class=HTMLResponse)
async def new_order_form(request: Request, trace_id: str | None = Query(None)):
    raise NotImplementedError


# PSEUDO:
# - user = require_login(request)
# - form = parse body (text, confirm?, trace_id?)
# - if confirm: result = await invoke_director("nl_ordering", {...confirm:true, trace_id})
#   else:      result = await invoke_director("nl_ordering", {text, user_id, facility_id})
# - if result.status == "awaiting_confirmation": re-render orders/new.html with proposal card
# - if result.status == "pending": redirect to /orders/{order_id}
@router.post("/orders/new", response_class=HTMLResponse)
async def submit_order(request: Request):
    raise NotImplementedError


@api_router.post("/orders")
async def create_order_json(request: Request):
    raise NotImplementedError


# Phase 2 Graduation:
#   - Add /orders/{id}/cancel route. Seam: services.orders.advance_order_status(id, "cancelled").
#   - Status transitions emit Inngest events. Seam: services.orders.advance_order_status() body.
