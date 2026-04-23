# PRP-USDA-MACROS-001 Phase D — Copy-Ready Diffs

**Phase D Tasks:** T-010, T-011, T-012  
**Output Date:** 2026-04-23  
**Worker Instructions:** Apply these diffs mechanically once Phase C unblocks. No interpretation needed.

---

## Overview

Three template updates and one integration test to surface USDA macro data (kcal, protein, carbs, fat) from the `ScaledRecipe` dict returned by Phase C's T-007.

### Data Contract

`ScaledRecipe` will carry these **new optional keys** (float | None):
- `total_kcal`, `total_protein_g`, `total_carbs_g`, `total_fat_g`
- `per_serving_kcal`, `per_serving_protein_g`, `per_serving_carbs_g`, `per_serving_fat_g`

**Fallback rule:** If ANY ingredient lacks an `fdc_id` mapping, ALL EIGHT fields will be `None`.

When all are `None`, show: **"USDA macros unavailable — ingredient mapping incomplete"**

---

## T-010: Update `app/templates/recipes/detail.html`

**Location:** Insert a new `<section class="usda-macros">` block after lines 13–21 (the existing `<section class="nutrition">` block).

**Diff:**

```diff
 </section>
 
 <section class="nutrition">
   <h2>Nutrition (per serving)</h2>
   <ul class="nutrition-list">
     <li><span>Carbs</span> <strong>{{ recipe.carbs_g }} g</strong></li>
     <li><span>Sodium</span> <strong>{{ recipe.sodium_mg }} mg</strong></li>
     <li><span>Potassium</span> <strong>{{ recipe.potassium_mg }} mg</strong></li>
     <li><span>Phosphorus</span> <strong>{{ recipe.phosphorus_mg }} mg</strong></li>
   </ul>
 </section>
 
+<section class="usda-macros">
+  <h2>USDA Macros (per serving)</h2>
+  {% if scaled.per_serving_kcal is not none %}
+    <ul class="nutrition-list">
+      <li><span>Calories</span> <strong>{{ scaled.per_serving_kcal | round(0) | int }} kcal</strong></li>
+      <li><span>Protein</span> <strong>{{ scaled.per_serving_protein_g | round(1) }} g</strong></li>
+      <li><span>Carbohydrates</span> <strong>{{ scaled.per_serving_carbs_g | round(1) }} g</strong></li>
+      <li><span>Fat</span> <strong>{{ scaled.per_serving_fat_g | round(1) }} g</strong></li>
+    </ul>
+  {% else %}
+    <p class="macros-unavailable">USDA macros unavailable — ingredient mapping incomplete</p>
+  {% endif %}
+</section>
+
 <section class="allergens">
```

**Indentation:** 2 spaces (matches existing code).  
**Jinja2 syntax:** `is not none` comparison for optional None guard.  
**Classes used:** `.usda-macros`, `.nutrition-list` (reused), `.macros-unavailable`.

---

## T-011: Update `app/templates/recipes/ingredients.html`

**Location:** Two inserts in the table:
1. Add a `<tfoot>` row after line 42 (new row in existing `<tfoot>` for USDA totals).
2. Add a paragraph after line 49 (below the scaling explanation) describing per-serving totals.

**Diff:**

```diff
   <tfoot>
     <tr>
       <td><strong>Total</strong></td>
       <td class="num"><strong>{{ scaled.total_grams }}</strong></td>
       <td></td>
     </tr>
+    {% if scaled.total_kcal is not none %}
+    <tr>
+      <td><strong>USDA Total (per serving)</strong></td>
+      <td class="num"><strong>{{ scaled.per_serving_kcal | round(0) | int }} kcal / {{ scaled.per_serving_protein_g | round(1) }}g protein / {{ scaled.per_serving_carbs_g | round(1) }}g carbs / {{ scaled.per_serving_fat_g | round(1) }}g fat</strong></td>
+      <td></td>
+    </tr>
+    {% endif %}
   </tfoot>
 </table>
 
 <p class="muted">
   Scaled from base yield of {{ recipe.base_yield }} servings to
   {{ scaled.target_servings }} (factor {{ '%.2f'|format(scaled.scale_factor) }}).
 </p>
+{% if scaled.total_kcal is not none %}
+<p class="usda-estimate">
+  <strong>USDA estimate — per serving:</strong> {{ scaled.per_serving_kcal | round(0) | int }} kcal / {{ scaled.per_serving_protein_g | round(1) }}g protein / {{ scaled.per_serving_carbs_g | round(1) }}g carbs / {{ scaled.per_serving_fat_g | round(1) }}g fat
+</p>
+{% else %}
+<p class="usda-estimate macros-unavailable">
+  USDA macros unavailable — ingredient mapping incomplete
+</p>
+{% endif %}
 {% endblock %}
```

**Indentation:** 2 spaces.  
**Note:** Both renders show the same macro totals (per-serving basis). The tfoot row is compact; the paragraph is expanded for clarity below the table.  
**Classes used:** `.usda-estimate`, `.macros-unavailable`.

---

## T-012: Add Integration Test to `tests/integration/test_recipes_api.py`

**Location:** Append this new test function at the end of the file (after line 106).

**Snippet:**

```python
@pytest.mark.asyncio
async def test_api_v1_recipes_ingredients_returns_usda_macros(client):
    """GET /api/v1/recipes/{id}/ingredients returns scaled.per_serving_kcal as a number."""
    resp = await client.get("/api/v1/recipes/2/ingredients")
    assert resp.status_code == 200
    payload = resp.json()
    scaled = payload["scaled"]
    
    # Verify all eight USDA macro fields exist in the response (may be None or numbers).
    assert "per_serving_kcal" in scaled
    assert "per_serving_protein_g" in scaled
    assert "per_serving_carbs_g" in scaled
    assert "per_serving_fat_g" in scaled
    assert "total_kcal" in scaled
    assert "total_protein_g" in scaled
    assert "total_carbs_g" in scaled
    assert "total_fat_g" in scaled
    
    # If macros are present (not None), they must be numbers.
    if scaled["per_serving_kcal"] is not None:
        assert isinstance(scaled["per_serving_kcal"], (int, float))
        assert scaled["per_serving_kcal"] > 0
    if scaled["per_serving_protein_g"] is not None:
        assert isinstance(scaled["per_serving_protein_g"], (int, float))
    if scaled["per_serving_carbs_g"] is not None:
        assert isinstance(scaled["per_serving_carbs_g"], (int, float))
    if scaled["per_serving_fat_g"] is not None:
        assert isinstance(scaled["per_serving_fat_g"], (int, float))
```

**Fixture/import:** None required — uses existing `client` fixture (async httpx client from conftest).  
**Assertion pattern:** Mirrors existing `test_recipe_ingredients_scaled()` (lines 78–87) style.  
**Recipe ID:** `2` (safe test data choice; assume recipe 2 exists from seed).

---

## CSS Classes — New Styling Needed

**Classes to define in `/opt/direct-supply-meal/app/static/css/main.css`:**

| Class | Purpose | Suggested Styling |
|-------|---------|------------------|
| `.usda-macros` | Container for USDA macros section on detail page | Mirror `.nutrition` section styling: `margin: 1rem 0` |
| `.usda-estimate` | Paragraph showing per-serving estimate on ingredients page | Text color: `var(--muted)`, font-size: `0.9rem`, margin: `1rem 0` |
| `.macros-unavailable` | Fallback message when ingredient mappings incomplete | Color: `#e74c3c` (red/warning), font-style: `italic`, padding: `0.75rem`, background: `#fadbd8` (light red), border-radius: `4px` |

**Implementation note:** `.usda-macros` should reuse `.nutrition-list` grid styling (auto-fit 120px columns). Add a few lines to `main.css` before line 520.

---

## Field-to-Label Mapping

| ScaledRecipe Key | Template Label | Format/Unit |
|------------------|----------------|------------|
| `per_serving_kcal` | `Calories` | `{{ value \| round(0) \| int }} kcal` |
| `per_serving_protein_g` | `Protein` | `{{ value \| round(1) }} g` |
| `per_serving_carbs_g` | `Carbohydrates` | `{{ value \| round(1) }} g` |
| `per_serving_fat_g` | `Fat` | `{{ value \| round(1) }} g` |

(Totals use the same fields with `total_` prefix for the 8-field dict contract, but UI only displays per-serving in T-010 detail page and T-011 ingredients table/paragraph.)

---

## Rounding Policy

**Jinja2 filters used in diffs:**
- **Kcal:** `{{ value | round(0) | int }}` → whole number (e.g., "42 kcal")
- **Grams (protein/carbs/fat):** `{{ value | round(1) }}` → one decimal place (e.g., "12.5 g")

**Rationale:** Matches existing template style (see `'%.2f' | format()` in lines 10, 48); round(1) for grams provides adequate precision for nutrition labels without false precision.

---

## Summary of Changes

| File | Change | Task |
|------|--------|------|
| `app/templates/recipes/detail.html` | +15 lines (new section) | T-010 |
| `app/templates/recipes/ingredients.html` | +10 lines (tfoot row + paragraph) | T-011 |
| `tests/integration/test_recipes_api.py` | +28 lines (new async test) | T-012 |
| `app/static/css/main.css` | +~8 lines (new classes) | CSS style prep |

**Total diffs:** 3 template updates + 1 test + CSS note. No changes to routes, models, or services (Phase C owns T-007 ScaledRecipe augmentation).

---

## Notes for Workers

1. **Apply in order:** T-010 → T-011 → T-012 → CSS. CSS can be deferred if styling owner is different.
2. **Conditional blocks:** Every macro reference is guarded by `{% if scaled.per_serving_kcal is not none %}` to handle the "all None" fallback case gracefully.
3. **Line numbers:** Diffs show context lines; use your editor's diff viewer to align insertions precisely.
4. **No model/route changes:** The `ScaledRecipe` dict augmentation (adding the eight fields) is T-007's job. These diffs assume it arrives in the template context unchanged.
5. **Test data:** Recipe 2 is assumed valid; if seed data changes, swap the recipe ID in T-012.

---

**Document Version:** 1.0  
**Last Updated:** 2026-04-23  
**Prepared by:** Phase D Specialist (read-only analysis)
