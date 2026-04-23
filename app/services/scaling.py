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
from typing import NotRequired, TypedDict


class ScaledIngredient(TypedDict):
    ingredient_id: int
    name: str
    grams: int
    allergen_tags: list[str]


class MacrosRow(TypedDict):
    """Per-100g macronutrient row for a single USDA food.

    Keys mirror the four per-100g columns on ``app.models.usda_food.UsdaFood``.
    Values are carried straight through from USDA FoodData Central (2-decimal
    precision) — no rounding applied at this layer.
    """

    kcal_per_100g: float
    protein_g_per_100g: float
    carbs_g_per_100g: float
    fat_g_per_100g: float


class ScaledRecipe(TypedDict):
    recipe_id: int
    title: str
    base_yield: int
    target_servings: int
    scale_factor: float
    ingredients: list[ScaledIngredient]
    total_grams: int
    # Optional macro rollups — present only when ``macros_lookup`` is passed to
    # ``scale_recipe``. All 8 keys are added together (all-or-nothing) so callers
    # can rely on a stable shape. When coverage is incomplete (any ingredient
    # missing from the lookup) each value is ``None`` per PRP D12.
    total_kcal: NotRequired[float | None]
    total_protein_g: NotRequired[float | None]
    total_carbs_g: NotRequired[float | None]
    total_fat_g: NotRequired[float | None]
    per_serving_kcal: NotRequired[float | None]
    per_serving_protein_g: NotRequired[float | None]
    per_serving_carbs_g: NotRequired[float | None]
    per_serving_fat_g: NotRequired[float | None]


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
    macros_lookup: dict[int, MacrosRow] | None = None,
) -> ScaledRecipe:
    """Scale a recipe to a target serving count (pure function, no I/O).

    Args:
        recipe_id: Recipe primary key (passed through to the result).
        title: Recipe display name (passed through to the result).
        base_yield: Serving count the ``ingredients`` grams are specified for.
        target_servings: Desired serving count; scale factor = ``target / base``.
        ingredients: Per-ingredient base-gram rows built by the caller.
        macros_lookup: Optional ``ingredient_id -> MacrosRow`` map used to roll up
            per-recipe macros. Semantics:

            - ``None`` (default): no macro keys are added to the result dict —
              backward-compat for existing callers.
            - Provided but any ingredient's ``ingredient_id`` is missing from the
              map: all 8 macro fields are set to ``None`` (the explicit
              coverage-incomplete path, PRP D12).
            - Provided and covers every ingredient: macro fields are populated
              with real summed values (no rounding — floats preserve precision).

    Returns:
        ``ScaledRecipe`` TypedDict. Macro keys present iff ``macros_lookup`` is
        non-None.

    Raises:
        ValueError: if ``target_servings`` or ``base_yield`` <= 0.
    """
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
    result = ScaledRecipe(
        recipe_id=recipe_id,
        title=title,
        base_yield=base_yield,
        target_servings=target_servings,
        scale_factor=scale_factor,
        ingredients=scaled,
        total_grams=sum(i["grams"] for i in scaled),
    )

    if macros_lookup is None:
        # Backward-compat path — no macro keys added.
        return result

    # Coverage check: every ingredient must have an entry in the lookup.
    coverage_complete = all(ing.ingredient_id in macros_lookup for ing in ingredients)

    if not coverage_complete:
        # PRP D12: explicit coverage-incomplete path — all 8 fields None.
        result["total_kcal"] = None
        result["total_protein_g"] = None
        result["total_carbs_g"] = None
        result["total_fat_g"] = None
        result["per_serving_kcal"] = None
        result["per_serving_protein_g"] = None
        result["per_serving_carbs_g"] = None
        result["per_serving_fat_g"] = None
        return result

    # T-USDA-MACROS-007: per-ingredient macros summation (post-PHASE-GATE-1).
    # For each scaled ingredient: contribution = grams_scaled * per_100g / 100.0.
    # No rounding during accumulation — preserve USDA float precision; templates
    # and tests round at display/assertion time.
    accumulated_kcal = 0.0
    accumulated_protein_g = 0.0
    accumulated_carbs_g = 0.0
    accumulated_fat_g = 0.0

    for scaled_ing in scaled:
        row = macros_lookup[scaled_ing["ingredient_id"]]
        factor = scaled_ing["grams"] / 100.0
        accumulated_kcal += row["kcal_per_100g"] * factor
        accumulated_protein_g += row["protein_g_per_100g"] * factor
        accumulated_carbs_g += row["carbs_g_per_100g"] * factor
        accumulated_fat_g += row["fat_g_per_100g"] * factor

    result["total_kcal"] = accumulated_kcal
    result["total_protein_g"] = accumulated_protein_g
    result["total_carbs_g"] = accumulated_carbs_g
    result["total_fat_g"] = accumulated_fat_g
    result["per_serving_kcal"] = accumulated_kcal / target_servings
    result["per_serving_protein_g"] = accumulated_protein_g / target_servings
    result["per_serving_carbs_g"] = accumulated_carbs_g / target_servings
    result["per_serving_fat_g"] = accumulated_fat_g / target_servings
    return result


# Phase 2 Graduation: add unit-of-measure engine (tsp/cup/oz) with locale-aware formatting.
