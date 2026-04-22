"""
PSEUDOCODE:
1. Agentic endpoint surface — POST /agents/menu-plan and POST /agents/nl-order.
2. Each dispatches to agents.drivers.dispatch.invoke_director().
3. Depth score computed via agents.depth_scorer.score_query() before dispatch (logged on trace row; Phase 2 seam acts on high scores).
4. /api/v1/agents/menu-plan + /api/v1/agents/nl-order JSON twins.
5. Gated — require_login. User.facility_id flows into the payload.
6. Fallback: if LLM returns AnthropicAPIError, use services.menu_fallback.generate_fallback_menu (for menu planner) or return an error card directing to /orders/new?mode=form (for nl_ordering).

IMPLEMENTATION: Phase 4.

Contract: docs/workflows/AGENT-WORKFLOW.md §§3-4, §8 fallback.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

# from app.auth.dependencies import require_login
# from agents.drivers.dispatch import invoke_director
# from agents.depth_scorer import score_query

router = APIRouter()
api_router = APIRouter(prefix="/api/v1")


# PSEUDO:
# - user = require_login(request)
# - payload = parse body (week_start, budget_cents, census, headcount)
# - level, n_agents, shape = score_query(describe(payload))  # advisory; logged on trace
# - result = await invoke_director("menu_planner", {facility_id: user.facility_id, **payload})
# - return HTML render of meal_plans/new.html with the result, or redirect to detail
@router.post("/agents/menu-plan", response_class=HTMLResponse)
async def menu_plan_html(request: Request):
    raise NotImplementedError


@api_router.post("/agents/menu-plan")
async def menu_plan_json(request: Request):
    raise NotImplementedError


# PSEUDO:
# - user = require_login(request)
# - payload = parse body (text, confirm?, trace_id?)
# - result = await invoke_director("nl_ordering", {user_id, facility_id, **payload})
# - HTML response: awaiting_confirmation → confirmation card; pending → redirect /orders/{id}
@router.post("/agents/nl-order", response_class=HTMLResponse)
async def nl_order_html(request: Request):
    raise NotImplementedError


@api_router.post("/agents/nl-order")
async def nl_order_json(request: Request):
    raise NotImplementedError


# Phase 2 Graduation:
#   - Depth score >= 7 actually decomposes (today: logs only). Seam: depth_scorer.should_decompose().
#   - SSE streaming of agent progress. Seam: new /agents/*/stream endpoints.
