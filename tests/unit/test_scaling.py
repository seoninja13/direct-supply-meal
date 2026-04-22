"""Unit tests for app.services.scaling — pure function, no I/O."""

from __future__ import annotations

import pytest

from app.services.scaling import IngredientRow, scale_recipe


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
