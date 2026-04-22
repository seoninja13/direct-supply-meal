"""
PSEUDOCODE:
1. Public recipe browsing routes (the kata baseline + JSON twins).
2. GET /recipes → list all 10 recipes. Jinja renders list.html.
3. GET /recipes/{id} → detail page with metadata and default-yield ingredients.
4. GET /recipes/{id}/ingredients → ingredients table; honors ?servings=N for on-the-fly scaling via app.services.scaling.
5. All three HTML routes have JSON twins under /api/v1/ that return the same data as JSON.
6. No auth required. Static pricing (cost_cents_per_serving from Recipe row) — never calls the LLM.

IMPLEMENTATION: Phase 4.

Contract: docs/workflows/DOMAIN-WORKFLOW.md §4 J1, PROTOCOL-APPLICATION-MATRIX.md P14.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()
api_router = APIRouter(prefix="/api/v1")


# PSEUDO:
# - session = get_session(); recipes = await db_list_recipes(session)
# - return Jinja render of list.html with recipes + static per-serving prices.
@router.get("/recipes", response_class=HTMLResponse)
async def list_recipes(request: Request):
    raise NotImplementedError


@api_router.get("/recipes")
async def list_recipes_json():
    raise NotImplementedError


# PSEUDO: fetch Recipe by id, 404 on miss, render detail.html.
@router.get("/recipes/{recipe_id}", response_class=HTMLResponse)
async def recipe_detail(request: Request, recipe_id: int):
    raise NotImplementedError


@api_router.get("/recipes/{recipe_id}")
async def recipe_detail_json(recipe_id: int):
    raise NotImplementedError


# PSEUDO:
# - servings = query param, default = recipe.base_yield
# - scaled = app.services.scaling.scale_recipe(recipe, servings)
# - render ingredients.html
@router.get("/recipes/{recipe_id}/ingredients", response_class=HTMLResponse)
async def recipe_ingredients(request: Request, recipe_id: int, servings: int | None = Query(None)):
    raise NotImplementedError


@api_router.get("/recipes/{recipe_id}/ingredients")
async def recipe_ingredients_json(recipe_id: int, servings: int | None = Query(None)):
    raise NotImplementedError


# Phase 2 Graduation:
#   - Add search endpoint /recipes/search (FTS5); seam is new query handler, existing routes unchanged.
