"""
PSEUDOCODE:
1. Pure, deterministic ingredient-gram scaling for a Recipe.
   Given a target serving count, compute a scaled version of every
   RecipeIngredient row using the ratio target / base_yield.
2. Callers (route handlers, @tool wrappers) are responsible for loading the Recipe
   row + its associated (RecipeIngredient, Ingredient) pairs and passing them in.
   This keeps scale_recipe() truly pure — no session, no I/O, fully testable.
3. target_servings <= 0 → ValueError.

IMPLEMENTATION: Phase 4.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


class ScaledIngredient(TypedDict):
    ingredient_id: int
    name: str
    grams: int
    allergen_tags: list[str]


class ScaledRecipe(TypedDict):
    recipe_id: int
    title: str
    base_yield: int
    target_servings: int
    scale_factor: float
    ingredients: list[ScaledIngredient]
    total_grams: int


@dataclass(frozen=True)
class IngredientRow:
    """Pure data carrier for scaling — route handlers build this list from DB."""

    ingredient_id: int
    name: str
    base_grams: int
    allergen_tags: list[str]


def scale_recipe(
    *,
    recipe_id: int,
    title: str,
    base_yield: int,
    target_servings: int,
    ingredients: list[IngredientRow],
) -> ScaledRecipe:
    if target_servings <= 0:
        raise ValueError(f"target_servings must be > 0, got {target_servings}")
    if base_yield <= 0:
        raise ValueError(f"recipe base_yield must be > 0, got {base_yield}")

    scale_factor = target_servings / base_yield
    scaled: list[ScaledIngredient] = [
        ScaledIngredient(
            ingredient_id=ing.ingredient_id,
            name=ing.name,
            grams=round(ing.base_grams * scale_factor),
            allergen_tags=list(ing.allergen_tags),
        )
        for ing in ingredients
    ]
    return ScaledRecipe(
        recipe_id=recipe_id,
        title=title,
        base_yield=base_yield,
        target_servings=target_servings,
        scale_factor=scale_factor,
        ingredients=scaled,
        total_grams=sum(i["grams"] for i in scaled),
    )


# Phase 2 Graduation: add unit-of-measure engine (tsp/cup/oz) with locale-aware formatting.
