"""
PSEUDOCODE:
1. Purpose: Pure, deterministic ingredient-gram scaling for a Recipe.
   Given a target serving count, compute a scaled version of every
   RecipeIngredient row using the ratio target / base_yield. Used by
   the recipe detail page (J1) and by the NL Ordering + Menu Planner
   agents via @tool wrappers.
2. Ordered algorithm:
   a. Load Recipe by id (expected to carry base_yield and prefetched
      recipe_ingredients with joined Ingredient rows).
   b. Reject target_servings <= 0 with ValueError.
   c. Compute scale_factor = target_servings / recipe.base_yield
      as a float.
   d. For each recipe_ingredient:
        scaled_grams = round(ri.grams * scale_factor)   # 1g precision
      Build a ScaledIngredient dict
      {ingredient_id, name, grams, allergen_tags}.
   e. Return a ScaledRecipe dict
      {
        recipe_id, title, base_yield, target_servings,
        scale_factor, ingredients: [ScaledIngredient, ...],
        total_grams: sum(grams)
      }.
3. Inputs / Outputs:
   - Input: Recipe (with .recipe_ingredients relationship loaded),
            int target_servings.
   - Output: ScaledRecipe dict (see above).
4. Side effects: None. Pure function. No DB writes, no LLM calls.

IMPLEMENTATION: Phase 4.
"""

from __future__ import annotations

from typing import Any, TypedDict


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


def scale_recipe(recipe: Any, target_servings: int) -> ScaledRecipe:
    # PSEUDO:
    #   1. if target_servings <= 0: raise ValueError
    #   2. scale_factor = target_servings / recipe.base_yield
    #   3. ingredients = []
    #      for ri in recipe.recipe_ingredients:      # from app.models.recipe
    #          scaled = round(ri.grams * scale_factor)
    #          ingredients.append({
    #              "ingredient_id": ri.ingredient_id,
    #              "name":          ri.ingredient.name,
    #              "grams":         scaled,
    #              "allergen_tags": ri.ingredient.allergen_tags,
    #          })
    #   4. total = sum(i["grams"] for i in ingredients)
    #   5. return ScaledRecipe(
    #        recipe_id=recipe.id, title=recipe.title,
    #        base_yield=recipe.base_yield,
    #        target_servings=target_servings,
    #        scale_factor=scale_factor,
    #        ingredients=ingredients, total_grams=total,
    #      )
    raise NotImplementedError("Phase 4")


# Phase 2 Graduation: services/scaling.py::scale_recipe() — swap grams-rounding
# for a unit-of-measure engine (tsp/cup/oz) with locale-aware formatting.
