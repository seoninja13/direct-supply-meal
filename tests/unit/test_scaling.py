"""Unit tests for app.services.scaling — pure function, no I/O."""

from __future__ import annotations

import pytest

from app.services.scaling import IngredientRow, MacrosRow, scale_recipe


def _sample_ingredients() -> list[IngredientRow]:
    return [
        IngredientRow(ingredient_id=1, name="oats", base_grams=160, allergen_tags=["gluten"]),
        IngredientRow(ingredient_id=2, name="almond milk", base_grams=1000, allergen_tags=["nuts"]),
        IngredientRow(ingredient_id=3, name="chia seeds", base_grams=70, allergen_tags=[]),
    ]


def test_scale_at_base_yield_returns_unchanged_grams():
    result = scale_recipe(
        recipe_id=3,
        title="Overnight Oats",
        base_yield=4,
        target_servings=4,
        ingredients=_sample_ingredients(),
    )
    assert result["scale_factor"] == 1.0
    assert result["total_grams"] == 1230
    assert [i["grams"] for i in result["ingredients"]] == [160, 1000, 70]


def test_scale_2x_doubles_grams():
    result = scale_recipe(
        recipe_id=3,
        title="Overnight Oats",
        base_yield=4,
        target_servings=8,
        ingredients=_sample_ingredients(),
    )
    assert result["scale_factor"] == 2.0
    assert result["total_grams"] == 2460
    assert [i["grams"] for i in result["ingredients"]] == [320, 2000, 140]


def test_scale_half_halves_grams():
    result = scale_recipe(
        recipe_id=3,
        title="Overnight Oats",
        base_yield=4,
        target_servings=2,
        ingredients=_sample_ingredients(),
    )
    assert result["scale_factor"] == 0.5
    assert [i["grams"] for i in result["ingredients"]] == [80, 500, 35]


def test_invalid_target_raises():
    with pytest.raises(ValueError):
        scale_recipe(
            recipe_id=3,
            title="x",
            base_yield=4,
            target_servings=0,
            ingredients=_sample_ingredients(),
        )


def test_allergen_tags_preserved():
    result = scale_recipe(
        recipe_id=3,
        title="Overnight Oats",
        base_yield=4,
        target_servings=4,
        ingredients=_sample_ingredients(),
    )
    assert result["ingredients"][0]["allergen_tags"] == ["gluten"]
    assert result["ingredients"][1]["allergen_tags"] == ["nuts"]
    assert result["ingredients"][2]["allergen_tags"] == []


# ---------------------------------------------------------------------------
# T-USDA-MACROS-007/008 — macros_lookup scaffolds
# ---------------------------------------------------------------------------

_MACRO_KEYS = (
    "total_kcal",
    "total_protein_g",
    "total_carbs_g",
    "total_fat_g",
    "per_serving_kcal",
    "per_serving_protein_g",
    "per_serving_carbs_g",
    "per_serving_fat_g",
)


@pytest.mark.skip(
    reason="T-USDA-MACROS-008 math fill-in pending PHASE-GATE-1 Veggie Omelette values from T-006"
)
def test_veggie_omelette_base_yield_macros_exact():
    """Given Veggie Omelette (recipe_id=2, base_yield=1) with T-006's macros_lookup,
    scale_recipe returns total + per-serving kcal/protein/carbs/fat matching hand-calc
    within tolerance 0.5. Fill expected values from the commit message of T-006."""
    pass


@pytest.mark.skip(reason="T-USDA-MACROS-008 math fill-in pending PHASE-GATE-1")
def test_macros_scale_linearly():
    """At target_servings = 2 * base_yield: totals double, per-serving unchanged."""
    pass


def test_missing_fdc_returns_none_totals():
    """If macros_lookup omits at least one ingredient_id, all 8 macro fields = None."""
    ingredients = [
        IngredientRow(ingredient_id=1, name="oats", base_grams=160, allergen_tags=[]),
        IngredientRow(ingredient_id=2, name="almond milk", base_grams=1000, allergen_tags=[]),
    ]
    # Lookup covers ingredient 1 only — ingredient 2 is missing.
    macros_lookup: dict[int, MacrosRow] = {
        1: MacrosRow(
            kcal_per_100g=389.0,
            protein_g_per_100g=16.9,
            carbs_g_per_100g=66.3,
            fat_g_per_100g=6.9,
        ),
    }
    result = scale_recipe(
        recipe_id=3,
        title="Overnight Oats",
        base_yield=4,
        target_servings=4,
        ingredients=ingredients,
        macros_lookup=macros_lookup,
    )
    for key in _MACRO_KEYS:
        assert key in result, f"missing key {key}"
        assert result[key] is None, f"expected {key} to be None, got {result[key]!r}"


def test_no_macros_lookup_preserves_existing_return_shape():
    """If macros_lookup is None (default), returned dict does NOT contain any macro keys.
    Backward compat for existing callers."""
    result = scale_recipe(
        recipe_id=3,
        title="Overnight Oats",
        base_yield=4,
        target_servings=4,
        ingredients=_sample_ingredients(),
    )
    for key in _MACRO_KEYS:
        assert key not in result, f"unexpected key {key} in backward-compat result"
