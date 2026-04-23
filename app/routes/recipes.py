"""
PSEUDOCODE:
1. Public recipe browsing (kata baseline) + JSON twins.
2. GET /recipes           → list 10 recipes.
3. GET /recipes/{id}      → recipe detail (metadata + default-yield ingredients).
4. GET /recipes/{id}/ingredients?servings=N → scaled ingredients via services.scaling.scale_recipe.
5. No auth. Static pricing from recipe.cost_cents_per_serving.

IMPLEMENTATION: Slice A.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.db.database import get_session
from app.models.recipe import Ingredient, Recipe, RecipeIngredient
from app.models.usda_food import UsdaFood
from app.services.scaling import IngredientRow, MacrosRow, scale_recipe

router = APIRouter()
api_router = APIRouter(prefix="/api/v1")


async def _list_recipes_data(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(Recipe).order_by(Recipe.title))
    recipes = result.scalars().all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "texture_level": r.texture_level,
            "allergens": r.allergens or [],
            "cost_cents_per_serving": r.cost_cents_per_serving,
            "prep_time_minutes": r.prep_time_minutes,
            "base_yield": r.base_yield,
        }
        for r in recipes
    ]


async def _get_recipe_with_ingredients(
    session: AsyncSession, recipe_id: int, target_servings: int | None
) -> dict:
    recipe = await session.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail=f"Recipe {recipe_id} not found")

    # Fetch RecipeIngredient rows joined to Ingredient.
    ri_result = await session.execute(
        select(RecipeIngredient, Ingredient)
        .join(Ingredient, RecipeIngredient.ingredient_id == Ingredient.id)
        .where(RecipeIngredient.recipe_id == recipe_id)
    )
    rows = ri_result.all()

    ingredients = [
        IngredientRow(
            ingredient_id=ing.id,
            name=ing.name,
            base_grams=ri.grams,
            allergen_tags=list(ing.allergen_tags or []),
        )
        for ri, ing in rows
    ]

    # T-USDA-MACROS-009: Collect fdc_ids present on ingredients and build
    # macros_lookup keyed by ingredient_id (NOT fdc_id). When no ingredients
    # have an fdc_id yet, pass None so the response dict has NO macro keys
    # (preserves pre-feature API shape). scale_recipe itself handles the
    # coverage-incomplete case per PRP D12.
    fdc_ids = {ing.fdc_id for _, ing in rows if ing.fdc_id is not None}
    usda_by_fdc: dict[int, UsdaFood] = {}
    if fdc_ids:
        usda_stmt = select(UsdaFood).where(col(UsdaFood.fdc_id).in_(fdc_ids))
        usda_result = await session.execute(usda_stmt)
        usda_by_fdc = {u.fdc_id: u for u in usda_result.scalars().all()}

    macros_lookup: dict[int, MacrosRow] = {}
    for _ri, ing in rows:
        if ing.fdc_id is not None and ing.fdc_id in usda_by_fdc:
            u = usda_by_fdc[ing.fdc_id]
            macros_lookup[ing.id] = MacrosRow(
                kcal_per_100g=u.kcal_per_100g,
                protein_g_per_100g=u.protein_g_per_100g,
                carbs_g_per_100g=u.carbs_g_per_100g,
                fat_g_per_100g=u.fat_g_per_100g,
            )

    servings = target_servings if target_servings and target_servings > 0 else recipe.base_yield
    scaled = scale_recipe(
        recipe_id=recipe.id,
        title=recipe.title,
        base_yield=recipe.base_yield,
        target_servings=servings,
        ingredients=ingredients,
        macros_lookup=macros_lookup if macros_lookup else None,
    )

    return {
        "recipe": {
            "id": recipe.id,
            "title": recipe.title,
            "texture_level": recipe.texture_level,
            "allergens": recipe.allergens or [],
            "cost_cents_per_serving": recipe.cost_cents_per_serving,
            "prep_time_minutes": recipe.prep_time_minutes,
            "base_yield": recipe.base_yield,
            "carbs_g": recipe.carbs_g,
            "sodium_mg": recipe.sodium_mg,
            "potassium_mg": recipe.potassium_mg,
            "phosphorus_mg": recipe.phosphorus_mg,
        },
        "scaled": scaled,
    }


# --- HTML routes ---------------------------------------------------------


@router.get("/recipes", response_class=HTMLResponse)
async def list_recipes(request: Request, session: AsyncSession = Depends(get_session)):
    recipes = await _list_recipes_data(session)
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="recipes/list.html",
        context={"page_title": "Recipes — ds-meal", "recipes": recipes, "user": None},
    )


@router.get("/recipes/{recipe_id}", response_class=HTMLResponse)
async def recipe_detail(
    request: Request, recipe_id: int, session: AsyncSession = Depends(get_session)
):
    payload = await _get_recipe_with_ingredients(session, recipe_id, target_servings=None)
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="recipes/detail.html",
        context={
            "page_title": f"{payload['recipe']['title']} — ds-meal",
            "recipe": payload["recipe"],
            "scaled": payload["scaled"],
            "user": None,
        },
    )


@router.get("/recipes/{recipe_id}/ingredients", response_class=HTMLResponse)
async def recipe_ingredients(
    request: Request,
    recipe_id: int,
    servings: int | None = Query(None, ge=1, le=10_000),
    session: AsyncSession = Depends(get_session),
):
    payload = await _get_recipe_with_ingredients(session, recipe_id, servings)
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="recipes/ingredients.html",
        context={
            "page_title": f"Ingredients — {payload['recipe']['title']}",
            "recipe": payload["recipe"],
            "scaled": payload["scaled"],
            "user": None,
        },
    )


# --- JSON twins ----------------------------------------------------------


@api_router.get("/recipes")
async def list_recipes_json(session: AsyncSession = Depends(get_session)):
    return JSONResponse({"recipes": await _list_recipes_data(session)})


@api_router.get("/recipes/{recipe_id}")
async def recipe_detail_json(recipe_id: int, session: AsyncSession = Depends(get_session)):
    return JSONResponse(await _get_recipe_with_ingredients(session, recipe_id, target_servings=None))


@api_router.get("/recipes/{recipe_id}/ingredients")
async def recipe_ingredients_json(
    recipe_id: int,
    servings: int | None = Query(None, ge=1, le=10_000),
    session: AsyncSession = Depends(get_session),
):
    return JSONResponse(await _get_recipe_with_ingredients(session, recipe_id, servings))


# Phase 2 Graduation: add /recipes/search (FTS5). Swap Jinja for React — same /api/v1/ endpoints.
