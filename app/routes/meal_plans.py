"""
PSEUDOCODE:
1. Gated weekly-meal-planning routes — Menu Planner agent surface.
2. GET /meal-plans — list MealPlans for the user's facility.
3. GET /meal-plans/new — wizard entry (pick week_start, budget, census, submit).
4. POST /meal-plans/new — invoke agents.drivers.dispatch.invoke_director("menu_planner", payload).
5. /api/v1/meal-plans twins for list and POST.
6. On successful save, MealPlan triggers services.orders.generate_from_meal_plan → daily Orders with status=pending.

IMPLEMENTATION: Phase 4.

Contract: docs/workflows/DOMAIN-WORKFLOW.md §4 J3, AGENT-WORKFLOW.md §3.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

# from app.auth.dependencies import require_login
# from agents.drivers.dispatch import invoke_director

router = APIRouter()
api_router = APIRouter(prefix="/api/v1")


# PSEUDO:
# - user = require_login(request)
# - plans = db_list_meal_plans(user.facility_id)
# - render meal_plans/list.html
@router.get("/meal-plans", response_class=HTMLResponse)
async def list_meal_plans(request: Request):
    raise NotImplementedError


@api_router.get("/meal-plans")
async def list_meal_plans_json():
    raise NotImplementedError


# PSEUDO: render empty wizard form (meal_plans/new.html).
@router.get("/meal-plans/new", response_class=HTMLResponse)
async def new_meal_plan_form(request: Request):
    raise NotImplementedError


# PSEUDO:
# - user = require_login(request)
# - form = parse POST body (week_start, budget_cents, census dict, headcount)
# - result = await invoke_director("menu_planner", {facility_id: user.facility_id, **form})
# - on success: invoke services.orders.generate_from_meal_plan(result.meal_plan_id); redirect to /meal-plans/{id}
# - on partial: re-render new.html with warnings inline
@router.post("/meal-plans/new", response_class=HTMLResponse)
async def submit_meal_plan(request: Request):
    raise NotImplementedError


@api_router.post("/meal-plans")
async def create_meal_plan_json(request: Request):
    raise NotImplementedError


# Phase 2 Graduation:
#   - Streaming agent progress over SSE. Seam: new /agents/menu-plan/stream endpoint.
#   - invoke_director() body swaps sync for Inngest.
