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


# ---------------------------------------------------------------------------
# Veggie Omelette hand-calc fixture (shared between T-008 gold-master tests).
# Per-100g values copied VERBATIM from
# docs/PRP-USDA-MACROS-001-VEGGIE-OMELETTE-HANDCALC.md so the tests lock in the
# values PHASE-GATE-1 approved. Salt & pepper is mapped to None fdc_id in the
# PoC fixture; per the hand-calc doc it contributes 0 to all four totals, so
# the synthetic test input omits it entirely (6 real ingredients, full macro
# coverage, math completes).
#
# Expected per-serving totals at base_yield=1, target_servings=1:
#   kcal=632.2, protein_g=22.513, carbs_g=73.789, fat_g=29.022
# ---------------------------------------------------------------------------


def _veggie_omelette_ingredients() -> list[IngredientRow]:
    """6 real (non-null-mapped) Veggie Omelette ingredients with base grams."""
    return [
        IngredientRow(ingredient_id=1, name="large eggs", base_grams=100, allergen_tags=["egg"]),
        IngredientRow(ingredient_id=2, name="diced onion", base_grams=40, allergen_tags=[]),
        IngredientRow(ingredient_id=3, name="diced tomato", base_grams=50, allergen_tags=[]),
        IngredientRow(ingredient_id=4, name="spinach leaves", base_grams=20, allergen_tags=[]),
        IngredientRow(ingredient_id=5, name="olive oil", base_grams=15, allergen_tags=[]),
        IngredientRow(
            ingredient_id=6, name="small corn tortillas", base_grams=150, allergen_tags=[]
        ),
    ]


def _veggie_omelette_macros_lookup() -> dict[int, MacrosRow]:
    """Per-100g macros for each of the 6 Veggie Omelette ingredients.

    Values are verbatim from the hand-calc doc
    (docs/PRP-USDA-MACROS-001-VEGGIE-OMELETTE-HANDCALC.md) — the numbers
    PHASE-GATE-1 approved.
    """
    return {
        1: MacrosRow(  # large eggs (FDC 171287 — Egg, whole, raw, fresh)
            kcal_per_100g=143.0,
            protein_g_per_100g=12.56,
            carbs_g_per_100g=0.72,
            fat_g_per_100g=9.51,
        ),
        2: MacrosRow(  # diced onion (FDC 170000 — Onions, raw)
            kcal_per_100g=39.0,
            protein_g_per_100g=0.98,
            carbs_g_per_100g=8.90,
            fat_g_per_100g=0.09,
        ),
        3: MacrosRow(  # diced tomato (FDC 170457)
            kcal_per_100g=18.0,
            protein_g_per_100g=0.88,
            carbs_g_per_100g=3.89,
            fat_g_per_100g=0.20,
        ),
        4: MacrosRow(  # spinach leaves (FDC 168462 — Spinach, raw)
            kcal_per_100g=25.0,
            protein_g_per_100g=2.855,
            carbs_g_per_100g=3.02,
            fat_g_per_100g=0.505,
        ),
        5: MacrosRow(  # olive oil (FDC 171413 — Oil, olive, salad or cooking)
            kcal_per_100g=884.0,
            protein_g_per_100g=0.0,
            carbs_g_per_100g=0.0,
            fat_g_per_100g=100.0,
        ),
        6: MacrosRow(  # small corn tortillas (FDC 2343303)
            kcal_per_100g=218.0,
            protein_g_per_100g=5.70,
            carbs_g_per_100g=44.64,
            fat_g_per_100g=2.85,
        ),
    }


def test_veggie_omelette_base_yield_macros_exact():
    """Gold-master: Veggie Omelette at base_yield=1, target_servings=1 matches hand-calc.

    Expected totals from docs/PRP-USDA-MACROS-001-VEGGIE-OMELETTE-HANDCALC.md:
      632.2 kcal, 22.513 g protein, 73.789 g carbs, 29.022 g fat per serving.
    Since base_yield == target_servings == 1, totals == per-serving values.
    """
    result = scale_recipe(
        recipe_id=2,
        title="Veggie Omelette",
        base_yield=1,
        target_servings=1,
        ingredients=_veggie_omelette_ingredients(),
        macros_lookup=_veggie_omelette_macros_lookup(),
    )

    # All 8 macro fields populated (non-None).
    for key in _MACRO_KEYS:
        assert key in result, f"missing key {key}"
        assert result[key] is not None, f"expected {key} to be non-None"

    # Totals match hand-calc (tolerance ±0.5 kcal, ±0.05 g per task spec).
    assert result["total_kcal"] == pytest.approx(632.2, abs=0.5)
    assert result["total_protein_g"] == pytest.approx(22.513, abs=0.05)
    assert result["total_carbs_g"] == pytest.approx(73.789, abs=0.05)
    assert result["total_fat_g"] == pytest.approx(29.022, abs=0.05)

    # Per-serving equals totals (target_servings = 1).
    assert result["per_serving_kcal"] == pytest.approx(result["total_kcal"], abs=1e-9)
    assert result["per_serving_protein_g"] == pytest.approx(result["total_protein_g"], abs=1e-9)
    assert result["per_serving_carbs_g"] == pytest.approx(result["total_carbs_g"], abs=1e-9)
    assert result["per_serving_fat_g"] == pytest.approx(result["total_fat_g"], abs=1e-9)


def test_macros_scale_linearly():
    """At target_servings = 2 * base_yield, totals double; per-serving stays invariant.

    Uses the same Veggie Omelette fixture as the gold-master test.
    """
    base = scale_recipe(
        recipe_id=2,
        title="Veggie Omelette",
        base_yield=1,
        target_servings=1,
        ingredients=_veggie_omelette_ingredients(),
        macros_lookup=_veggie_omelette_macros_lookup(),
    )
    doubled = scale_recipe(
        recipe_id=2,
        title="Veggie Omelette",
        base_yield=1,
        target_servings=2,
        ingredients=_veggie_omelette_ingredients(),
        macros_lookup=_veggie_omelette_macros_lookup(),
    )

    # Totals double (within float tolerance). Grams are integer-rounded per
    # ingredient inside scale_recipe; at 2x every base_grams is already an
    # integer and doubling is exact, so the math is exact too.
    assert doubled["total_kcal"] == pytest.approx(2 * base["total_kcal"], abs=1e-9)
    assert doubled["total_protein_g"] == pytest.approx(2 * base["total_protein_g"], abs=1e-9)
    assert doubled["total_carbs_g"] == pytest.approx(2 * base["total_carbs_g"], abs=1e-9)
    assert doubled["total_fat_g"] == pytest.approx(2 * base["total_fat_g"], abs=1e-9)

    # Per-serving invariant under scaling (total * 2 / 2 == total).
    assert doubled["per_serving_kcal"] == pytest.approx(base["per_serving_kcal"], abs=1e-9)
    assert doubled["per_serving_protein_g"] == pytest.approx(base["per_serving_protein_g"], abs=1e-9)
    assert doubled["per_serving_carbs_g"] == pytest.approx(base["per_serving_carbs_g"], abs=1e-9)
    assert doubled["per_serving_fat_g"] == pytest.approx(base["per_serving_fat_g"], abs=1e-9)


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
