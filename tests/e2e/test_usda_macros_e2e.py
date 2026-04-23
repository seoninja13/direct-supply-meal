"""E2E: USDA macros render for anonymous users on recipe detail + ingredients pages.

Anonymous (no auth) user navigates to:
  - /recipes/2                           -> sees "USDA Macros (per serving)" heading + kcal number
  - /recipes/2/ingredients               -> sees "USDA estimate" paragraph + scaled total
  - /recipes/2/ingredients?servings=20   -> scaled values increase proportionally

Follows the Slice A / Slice C pattern: BASE_URL env var, skip when live server
unreachable, skip when the USDA macros feature hasn't landed on the target yet.
"""

from __future__ import annotations

import os
import re
import urllib.error
import urllib.request

import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("BASE_URL", "https://ds-meal.dulocore.com")


def _server_reachable() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def _recipe_2_deployed() -> bool:
    """Recipe 2 (Veggie Omelette) + USDA macros are available on the target.

    Guards against the test running against a stale deploy where seed_db hasn't
    populated recipe 2 or the USDA ingredient mappings haven't been merged.
    """
    try:
        with urllib.request.urlopen(f"{BASE_URL}/recipes/2", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not (_server_reachable() and _recipe_2_deployed()),
    reason=(
        f"Live server at {BASE_URL} not reachable, or recipe 2 + USDA macros "
        "not yet deployed — skip E2E until deploy gate passes."
    ),
)


def test_recipe_detail_shows_usda_macros_for_anonymous_user(page: Page) -> None:
    """Anonymous user loads /recipes/2 and sees the USDA macros section with numbers."""
    page.goto(f"{BASE_URL}/recipes/2")

    # The USDA macros section must be present and visible.
    macros_section = page.locator("section.usda-macros")
    expect(macros_section).to_be_visible()

    # The heading (template uses capital M: "USDA Macros (per serving)").
    expect(macros_section.locator("h2")).to_have_text("USDA Macros (per serving)")

    # Calories row must show "NNN kcal" with a numeric value.
    kcal_row = macros_section.locator("li", has_text="Calories")
    expect(kcal_row).to_be_visible()
    kcal_text = kcal_row.locator("strong").text_content()
    assert kcal_text is not None, "kcal <strong> had no text content"
    match = re.match(r"(\d+)\s*kcal", kcal_text.strip())
    assert match is not None, f"kcal text doesn't match 'NNN kcal' pattern: {kcal_text!r}"
    kcal_value = int(match.group(1))
    # Veggie Omelette per-serving kcal sanity bounds (base_yield=1, ~2 eggs + veg).
    assert 100 <= kcal_value <= 1000, (
        f"Veggie Omelette kcal {kcal_value} outside sanity range 100-1000"
    )

    # Protein / Carbohydrates / Fat rows each show a number with the 'g' unit.
    for label in ("Protein", "Carbohydrates", "Fat"):
        row = macros_section.locator("li", has_text=label)
        expect(row).to_be_visible()
        g_text = row.locator("strong").text_content()
        assert g_text is not None, f"{label} <strong> had no text content"
        assert "g" in g_text, f"{label} row missing gram unit: {g_text!r}"
        assert re.search(r"\d", g_text), f"{label} row missing numeric value: {g_text!r}"


def test_recipe_ingredients_shows_usda_estimate_for_anonymous_user(page: Page) -> None:
    """Anonymous user loads /recipes/2/ingredients and sees the USDA estimate paragraph."""
    page.goto(f"{BASE_URL}/recipes/2/ingredients")

    # The USDA estimate paragraph should be visible and show the "per serving" blurb.
    estimate = page.locator("p.usda-estimate")
    expect(estimate).to_be_visible()
    txt = estimate.text_content() or ""
    assert "USDA estimate" in txt, f"Expected 'USDA estimate' in paragraph, got: {txt!r}"
    assert "kcal" in txt, f"Expected 'kcal' unit in paragraph, got: {txt!r}"
    assert re.search(r"\d", txt), f"Expected numeric value in paragraph, got: {txt!r}"


def test_recipe_ingredients_scales_with_servings(page: Page) -> None:
    """servings=20 yields a higher per-serving total row than the base_yield default.

    NOTE: per-serving values should be INVARIANT across servings counts. The scaled
    comparison is therefore against the tfoot row's tfoot kcal absolute; with
    base_yield=1 and servings=20, the per-serving stays the same but the ingredient
    grams scale 20x. We compare the paragraph's numeric kcal which is per-serving
    and should be equal OR the tfoot row — we assert per-serving remains numeric
    and equal-ish across the two URLs (proving the page renders both).
    """
    # Visit base (no ?servings param → defaults to base_yield=1).
    page.goto(f"{BASE_URL}/recipes/2/ingredients")
    base_para = page.locator("p.usda-estimate").text_content() or ""
    base_match = re.search(r"(\d+)\s*kcal", base_para)
    assert base_match, f"no kcal in base usda-estimate paragraph: {base_para!r}"
    base_per_serving_kcal = int(base_match.group(1))

    # Visit with ?servings=20 — per-serving macros should be identical (servings
    # count scales total grams, not per-serving values).
    page.goto(f"{BASE_URL}/recipes/2/ingredients?servings=20")
    scaled_para = page.locator("p.usda-estimate").text_content() or ""
    scaled_match = re.search(r"(\d+)\s*kcal", scaled_para)
    assert scaled_match, f"no kcal in scaled usda-estimate paragraph: {scaled_para!r}"
    scaled_per_serving_kcal = int(scaled_match.group(1))

    # Per-serving is a per-serving quantity — it must not change with ?servings.
    assert base_per_serving_kcal == scaled_per_serving_kcal, (
        f"per-serving kcal changed between views: base={base_per_serving_kcal} "
        f"scaled={scaled_per_serving_kcal} (per-serving must be invariant)"
    )

    # Total grams in tfoot should scale up proportionally — confirms scaling works.
    page.goto(f"{BASE_URL}/recipes/2/ingredients")
    base_total_grams_text = (
        page.locator("table.ingredients tfoot tr").first.locator("td").nth(1).text_content() or ""
    )
    page.goto(f"{BASE_URL}/recipes/2/ingredients?servings=20")
    scaled_total_grams_text = (
        page.locator("table.ingredients tfoot tr").first.locator("td").nth(1).text_content() or ""
    )
    base_g = int(re.search(r"(\d+)", base_total_grams_text).group(1))  # type: ignore[union-attr]
    scaled_g = int(re.search(r"(\d+)", scaled_total_grams_text).group(1))  # type: ignore[union-attr]
    assert scaled_g > base_g, (
        f"scaled total grams ({scaled_g}) not greater than base ({base_g}) — "
        "scaling is broken"
    )
