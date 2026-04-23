"""Integration tests — recipes routes hit a real SQLite + Jinja render."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "ds-meal"}


@pytest.mark.asyncio
async def test_api_v1_health(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_recipes_list_html_renders_10_rows(client):
    resp = await client.get("/recipes")
    assert resp.status_code == 200
    body = resp.text
    # Every recipe title appears in the HTML table.
    # Jinja auto-escapes & → &amp;, ' → &#39; when rendering into HTML; assert on
    # the escaped form to match what actually lands in the response body.
    for title in [
        "Chicken Stir-Fry",
        "Veggie Omelette",
        "Overnight Oats",
        "Baked Cod + Rice",
        "Beef Stew",
        "Pureed Chicken + Sweet Potato",
        "Turkey Meatloaf",
        "Lentil Soup",
        "Fruit &amp; Yogurt Parfait",
        "Shepherd&#39;s Pie",
    ]:
        assert title in body, f"Expected title {title!r} in /recipes HTML"


@pytest.mark.asyncio
async def test_api_v1_recipes_returns_10(client):
    resp = await client.get("/api/v1/recipes")
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload["recipes"]) == 10
    titles = {r["title"] for r in payload["recipes"]}
    assert "Overnight Oats" in titles
    assert "Chicken Stir-Fry" in titles


@pytest.mark.asyncio
async def test_recipe_detail_200(client):
    resp = await client.get("/recipes/3")
    assert resp.status_code == 200
    assert "Overnight Oats" in resp.text
    assert "carbs" in resp.text.lower() or "carbs_g" in resp.text.lower()


@pytest.mark.asyncio
async def test_recipe_detail_404(client):
    resp = await client.get("/recipes/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_recipe_ingredients_default_servings(client):
    resp = await client.get("/recipes/3/ingredients")
    assert resp.status_code == 200
    assert "oats" in resp.text.lower()


@pytest.mark.asyncio
async def test_recipe_ingredients_scaled(client):
    resp = await client.get("/api/v1/recipes/3/ingredients?servings=8")
    assert resp.status_code == 200
    payload = resp.json()
    scaled = payload["scaled"]
    assert scaled["target_servings"] == 8
    assert scaled["scale_factor"] == 2.0
    assert scaled["total_grams"] > 0
    # Overnight Oats base = 4 servings, base total = 1590g → 2x = 3180g
    assert scaled["total_grams"] == 3180


@pytest.mark.asyncio
async def test_json_twin_shape_parity(client):
    """HTML and JSON endpoints expose the same data set."""
    html_resp = await client.get("/recipes")
    json_resp = await client.get("/api/v1/recipes")
    assert html_resp.status_code == 200
    assert json_resp.status_code == 200
    # JSON returns a list of dicts whose title appears in the HTML (applying Jinja's
    # auto-escape: & → &amp; and ' → &#39;).
    def _escaped(s: str) -> str:
        return s.replace("&", "&amp;").replace("'", "&#39;")

    json_titles = [r["title"] for r in json_resp.json()["recipes"]]
    assert len(json_titles) == 10
    for t in json_titles:
        assert _escaped(t) in html_resp.text, f"Title {t!r} (escaped) not in HTML"


@pytest.mark.asyncio
async def test_api_v1_recipes_detail_includes_usda_macros(client):
    """Recipe 2 (Veggie Omelette) — when T-009 wires macros_lookup, keys appear and are numeric.

    Currently T-009 (route wiring) is not yet landed: scale_recipe is called without
    macros_lookup, so the 8 macro keys are omitted from ScaledRecipe (they are
    NotRequired). Once T-009 wires the route, the keys will be present and (for
    fully-mapped Recipe 2) numeric. This test exercises both states:

    - keys absent → skip (T-009 pending)
    - keys present, per_serving_kcal is None → coverage-incomplete path
    - keys present, per_serving_kcal is a number → validate numeric bounds
    """
    resp = await client.get("/api/v1/recipes/2")
    assert resp.status_code == 200
    payload = resp.json()
    scaled = payload["scaled"]

    macro_keys = (
        "total_kcal", "total_protein_g", "total_carbs_g", "total_fat_g",
        "per_serving_kcal", "per_serving_protein_g", "per_serving_carbs_g", "per_serving_fat_g",
    )
    if not any(k in scaled for k in macro_keys):
        pytest.skip("T-009 not yet wired: route does not pass macros_lookup to scale_recipe")

    # Once present, all 8 must be present together (stable shape contract per PRP D12).
    for key in macro_keys:
        assert key in scaled, f"Expected macro key {key!r} in scaled dict"

    if scaled["per_serving_kcal"] is not None:
        assert isinstance(scaled["per_serving_kcal"], (int, float))
        assert scaled["per_serving_kcal"] > 0
        assert scaled["per_serving_protein_g"] >= 0
        assert scaled["per_serving_carbs_g"] >= 0
        assert scaled["per_serving_fat_g"] >= 0
        # Sanity: Veggie Omelette should be ~300-1000 kcal per serving (hand-calc ≈ 632).
        assert 300 <= scaled["per_serving_kcal"] <= 1000
