"""
PSEUDOCODE:
1. Gated facility dashboard — what the admin sees immediately after sign-in.
2. GET /facility/dashboard: summary of active orders, next delivery, quick-reorder tiles.
3. /api/v1/facility/me: same data, JSON.
4. Uses require_login dependency (verifies Clerk JWT, loads User row, scopes to User.facility_id).
5. Inputs: no body. Outputs: dashboard context / JSON payload.
6. Side effects: read-only DB queries.

IMPLEMENTATION: Phase 4.

Contract: docs/workflows/DOMAIN-WORKFLOW.md §4 J2.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

# from app.auth.dependencies import require_login

router = APIRouter()
api_router = APIRouter(prefix="/api/v1")


# PSEUDO:
# - user = require_login(request)
# - active = services.orders.list_orders_for_facility(user.facility_id, status_filter={"pending","confirmed","in_preparation","out_for_delivery"}, page_size=5)
# - next_delivery = min(active, key=delivery_date)
# - recent_templates = most-ordered recipes in past 30 days
# - render facility/dashboard.html
@router.get("/facility/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    raise NotImplementedError


@api_router.get("/facility/me")
async def me_json():
    raise NotImplementedError


# Phase 2 Graduation:
#   - Add /facility/{id}/dashboard for multi-facility admins. Seam: require_login → require_role.
