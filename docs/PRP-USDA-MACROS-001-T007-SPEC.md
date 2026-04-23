# T-USDA-MACROS-007 Implementation Spec: scale_recipe() Macros Math Extension

**Status:** APPROVED  
**Task ID:** T-USDA-MACROS-007  
**Related PRP:** PRP-USDA-MACROS-001 §3 D5, D12  
**Date:** 2026-04-23  
**Owner:** Worker  
**Phase:** Phase C (Math + Tests)  

---

## 1. Current State

### Current `scale_recipe()` Signature

```python
def scale_recipe(
    *,
    recipe_id: int,
    title: str,
    base_yield: int,
    target_servings: int,
    ingredients: list[IngredientRow],
) -> ScaledRecipe:
```

### Current `ScaledRecipe` TypedDict

```python
class ScaledRecipe(TypedDict):
    recipe_id: int
    title: str
    base_yield: int
    target_servings: int
    scale_factor: float
    ingredients: list[ScaledIngredient]
    total_grams: int
```

### Current `ScaledIngredient` TypedDict

```python
class ScaledIngredient(TypedDict):
    ingredient_id: int
    name: str
    grams: int
    allergen_tags: list[str]
```

### Current `IngredientRow` Dataclass

```python
@dataclass(frozen=True)
class IngredientRow:
    """Pure data carrier for scaling — route handlers build this list from DB."""

    ingredient_id: int
    name: str
    base_grams: int
    allergen_tags: list[str]
```

---

## 2. New Signature After T-007

### New `scale_recipe()` Signature

```python
def scale_recipe(
    *,
    recipe_id: int,
    title: str,
    base_yield: int,
    target_servings: int,
    ingredients: list[IngredientRow],
    macros_lookup: dict[int, MacrosRow] | None = None,
) -> ScaledRecipe:
```

**Key changes:**
- Added optional kwarg `macros_lookup: dict[int, MacrosRow] | None = None`
- Dictionary key is `ingredient_id` (not `fdc_id`)
- Default is `None` for backward compatibility

### New `MacrosRow` TypedDict

```python
class MacrosRow(TypedDict):
    """Per-100g macronutrient values from USDA FoodData Central."""
    kcal_per_100g: float
    protein_g_per_100g: float
    carbs_g_per_100g: float
    fat_g_per_100g: float
```

**Rationale:** Mirrors `UsdaFood` model fields exactly. Type-safe structure for lookup values. Floats preserve USDA precision (typically 2 decimal places).

### New `ScaledRecipe` TypedDict

```python
class ScaledRecipe(TypedDict):
    recipe_id: int
    title: str
    base_yield: int
    target_servings: int
    scale_factor: float
    ingredients: list[ScaledIngredient]
    total_grams: int
    # New macros fields (all float | None):
    total_kcal: float | None
    total_protein_g: float | None
    total_carbs_g: float | None
    total_fat_g: float | None
    per_serving_kcal: float | None
    per_serving_protein_g: float | None
    per_serving_carbs_g: float | None
    per_serving_fat_g: float | None
```

**Eight new keys added:**
1. `total_kcal` — sum of all ingredient kcals (recipe total)
2. `total_protein_g` — sum of all ingredient protein (recipe total)
3. `total_carbs_g` — sum of all ingredient carbs (recipe total)
4. `total_fat_g` — sum of all ingredient fat (recipe total)
5. `per_serving_kcal` — `total_kcal / target_servings`
6. `per_serving_protein_g` — `total_protein_g / target_servings`
7. `per_serving_carbs_g` — `total_carbs_g / target_servings`
8. `per_serving_fat_g` — `total_fat_g / target_servings`

All eight fields are `float | None`. When `macros_lookup is None` or coverage is incomplete, all eight are `None`.

---

## 3. Math: Detailed Formulas

### Algorithm (pseudocode)

```
INPUTS:
  ingredients: list[IngredientRow]
  macros_lookup: dict[int, MacrosRow] | None
  target_servings: int

ALGORITHM:
  1. Initialize totals to 0.0:
     total_kcal = 0.0
     total_protein_g = 0.0
     total_carbs_g = 0.0
     total_fat_g = 0.0
     coverage_incomplete = False

  2. If macros_lookup is None:
     coverage_incomplete = True
     Jump to step 5

  3. For each scaled_ingredient in scaled_ingredients:
     ingredient_id = scaled_ingredient.ingredient_id
     grams_scaled = scaled_ingredient.grams

     macros = macros_lookup.get(ingredient_id)
     if macros is None:
       coverage_incomplete = True
       break out of loop

     kcal_i = grams_scaled * macros['kcal_per_100g'] / 100.0
     protein_i = grams_scaled * macros['protein_g_per_100g'] / 100.0
     carbs_i = grams_scaled * macros['carbs_g_per_100g'] / 100.0
     fat_i = grams_scaled * macros['fat_g_per_100g'] / 100.0

     total_kcal += kcal_i
     total_protein_g += protein_i
     total_carbs_g += carbs_i
     total_fat_g += fat_i

  4. If not coverage_incomplete:
     per_serving_kcal = total_kcal / target_servings
     per_serving_protein_g = total_protein_g / target_servings
     per_serving_carbs_g = total_carbs_g / target_servings
     per_serving_fat_g = total_fat_g / target_servings
  Else:
     per_serving_* = None for all four

  5. Set all eight fields in ScaledRecipe return dict

OUTPUTS:
  ScaledRecipe with all eight new fields populated (or None if coverage_incomplete)
```

### Step-by-step math for one ingredient example

**Example:**
- Ingredient: "Chicken breast"
  - `ingredient_id = 5`
  - `base_grams = 200` (from RecipeIngredient)
  - `target_servings = 4`
  - `scale_factor = 4 / recipe.base_yield` (assume = 1.5)
  - `grams_scaled = round(200 * 1.5) = 300`

- USDA data (from `macros_lookup[5]`):
  - `kcal_per_100g = 165.0`
  - `protein_g_per_100g = 31.0`
  - `carbs_g_per_100g = 0.0`
  - `fat_g_per_100g = 3.6`

**Calculation:**
```
kcal_i = 300 * 165.0 / 100.0 = 495.0
protein_i = 300 * 31.0 / 100.0 = 93.0
carbs_i = 300 * 0.0 / 100.0 = 0.0
fat_i = 300 * 3.6 / 100.0 = 10.8

Accumulate:
  total_kcal += 495.0
  total_protein_g += 93.0
  total_carbs_g += 0.0
  total_fat_g += 10.8
```

(Repeat for all ingredients, then divide by `target_servings`.)

### Float Precision

- All intermediate calculations use `float`.
- All macro totals stored as `float`.
- **No rounding during accumulation** — preserve USDA precision through summation.
- Templates / consumers round at **display time** (not in this function).
- Rationale: avoid cumulative rounding error across ingredient summation.

---

## 4. Backward Compatibility

### Existing Callers (No macros_lookup)

**Before T-007:**
```python
scaled = scale_recipe(
    recipe_id=recipe.id,
    title=recipe.title,
    base_yield=recipe.base_yield,
    target_servings=servings,
    ingredients=ingredients,
)
```

**After T-007 (same code still works):**
- Function signature accepts `macros_lookup=None` by default.
- All eight new fields are present in return dict, set to `None`.
- Existing consumer code that only reads `recipe_id, title, base_yield, target_servings, scale_factor, ingredients, total_grams` is unaffected.
- New consumer code can optionally check and display the eight new fields (all are `None` if no `macros_lookup` provided).

**No breaking change.** Return dict shape is supersetted; callers that don't use the new fields see no difference.

---

## 5. Purity Guarantee

The function **remains pure** after T-007:

1. **No DB access** — does not query `Ingredient`, `UsdaFood`, or any other table.
2. **No I/O** — does not read files, network, or system state.
3. **Deterministic** — given identical inputs, always returns identical output.
4. **No side effects** — does not mutate global state, doesn't log, doesn't cache.

**Rationale:** Caller (_get_recipe_with_ingredients in routes/recipes.py) is responsible for:
- Building `macros_lookup` dict from DB query (one SELECT per request).
- Passing the lookup dict into `scale_recipe()`.

This separation keeps scaling math pure and testable in isolation.

---

## 6. Error Handling

### Malformed `macros_lookup`

**Scenario:** `macros_lookup[5]` exists but is a dict missing required keys (e.g., missing `kcal_per_100g`).

**Behavior:** Function raises `KeyError` at first access attempt.
```python
# Inside the loop:
kcal_i = grams_scaled * macros['kcal_per_100g'] / 100.0  # KeyError if key missing
```

**Rationale (fail-fast):**
- Do not silently corrupt math by skipping the ingredient or returning partial totals.
- Raise immediately so the caller sees the error, not silently-wrong numbers.
- Typical case: route handler has a bug when building `macros_lookup`; the KeyError surfaces it.

**Mitigation (caller responsibility):**
- In T-009 (_get_recipe_with_ingredients), validate `macros_lookup` keys match the `MacrosRow` TypedDict.
- Or catch `KeyError` in route handler, log, and set `macros_lookup = None` (degrade to no-macros mode).

### Missing Ingredient in `macros_lookup`

**Scenario:** `macros_lookup.get(ingredient_id)` returns `None` (ingredient has no USDA mapping).

**Behavior:** Loop breaks, `coverage_incomplete = True`, all eight fields set to `None`.

**Rationale (PRP §3 D12):**
- Prevents silently-wrong totals (e.g., "123 kcal" when really 3 ingredients unmapped).
- Consumers (templates, JSON API) can check for `None` and display "USDA macros unavailable" badge.
- Conservative: prefer incomplete visibility over false precision.

---

## 7. Float vs Integer

### Storage

- **Macro totals:** stored as `float`.
- **Per-serving values:** `float`.
- **Scaling already uses `float`:** `scale_factor = target_servings / base_yield` is a float; `grams_scaled` is rounded to int for display, but intermediate `scale_factor` is float.

### Rationale

1. **Precision:** USDA per-100g values are floats (e.g., 165.0, 3.6, 31.0). Multiplying and summing floats preserves precision.
2. **No precision loss:** Rounding 495.0 kcal per ingredient and then summing introduces more error than summing first (float) and rounding at display time.
3. **Display time:** Templates/API consumers round or format (e.g., `{total_kcal:.1f}`) at render/JSON serialization.

**Example:**
```python
# In scaling.py — store float
total_kcal: float = 495.0 + 187.5 + 52.3 = 734.8
per_serving_kcal: float = 734.8 / 4 = 183.7

# In template — format at display
{{ scaled.per_serving_kcal | round(1) }}  {# renders "183.7" #}
```

---

## 8. Code Sketch: Drop-in Replacement

Below is a complete, mechanically-pasteable `scale_recipe()` function body that includes all new macros math. The worker should replace lines 47–78 of `app/services/scaling.py` with this:

```python
class MacrosRow(TypedDict):
    """Per-100g macronutrient values from USDA FoodData Central."""
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
    # New macros fields (all float | None):
    total_kcal: float | None
    total_protein_g: float | None
    total_carbs_g: float | None
    total_fat_g: float | None
    per_serving_kcal: float | None
    per_serving_protein_g: float | None
    per_serving_carbs_g: float | None
    per_serving_fat_g: float | None


def scale_recipe(
    *,
    recipe_id: int,
    title: str,
    base_yield: int,
    target_servings: int,
    ingredients: list[IngredientRow],
    macros_lookup: dict[int, MacrosRow] | None = None,
) -> ScaledRecipe:
    """
    Pure, deterministic ingredient-gram scaling with optional USDA macros summation.

    Inputs:
      recipe_id, title, base_yield: recipe metadata
      target_servings: desired serving count (must be > 0)
      ingredients: list of IngredientRow (base recipe structure)
      macros_lookup: optional dict[ingredient_id -> MacrosRow] for per-100g USDA values

    Outputs:
      ScaledRecipe with scaled ingredients + optional macros totals

    Error handling:
      - target_servings <= 0 or base_yield <= 0: ValueError
      - macros_lookup value missing required keys: KeyError (fail-fast)
      - ingredient missing from macros_lookup: set all 8 macro fields to None
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

    # Compute macro totals (if macros_lookup provided and complete).
    total_kcal: float | None = None
    total_protein_g: float | None = None
    total_carbs_g: float | None = None
    total_fat_g: float | None = None
    per_serving_kcal: float | None = None
    per_serving_protein_g: float | None = None
    per_serving_carbs_g: float | None = None
    per_serving_fat_g: float | None = None

    if macros_lookup is not None:
        coverage_incomplete = False
        accumulated_kcal = 0.0
        accumulated_protein_g = 0.0
        accumulated_carbs_g = 0.0
        accumulated_fat_g = 0.0

        for scaled_ing in scaled:
            ingredient_id = scaled_ing["ingredient_id"]
            grams_scaled = scaled_ing["grams"]

            macros = macros_lookup.get(ingredient_id)
            if macros is None:
                # Missing USDA mapping for this ingredient.
                coverage_incomplete = True
                break

            # Per-ingredient contribution: grams_scaled * (per_100g / 100)
            accumulated_kcal += grams_scaled * macros["kcal_per_100g"] / 100.0
            accumulated_protein_g += grams_scaled * macros["protein_g_per_100g"] / 100.0
            accumulated_carbs_g += grams_scaled * macros["carbs_g_per_100g"] / 100.0
            accumulated_fat_g += grams_scaled * macros["fat_g_per_100g"] / 100.0

        if not coverage_incomplete:
            # All ingredients had USDA data; compute totals and per-serving.
            total_kcal = accumulated_kcal
            total_protein_g = accumulated_protein_g
            total_carbs_g = accumulated_carbs_g
            total_fat_g = accumulated_fat_g
            per_serving_kcal = total_kcal / target_servings
            per_serving_protein_g = total_protein_g / target_servings
            per_serving_carbs_g = total_carbs_g / target_servings
            per_serving_fat_g = total_fat_g / target_servings

    return ScaledRecipe(
        recipe_id=recipe_id,
        title=title,
        base_yield=base_yield,
        target_servings=target_servings,
        scale_factor=scale_factor,
        ingredients=scaled,
        total_grams=sum(i["grams"] for i in scaled),
        total_kcal=total_kcal,
        total_protein_g=total_protein_g,
        total_carbs_g=total_carbs_g,
        total_fat_g=total_fat_g,
        per_serving_kcal=per_serving_kcal,
        per_serving_protein_g=per_serving_protein_g,
        per_serving_carbs_g=per_serving_carbs_g,
        per_serving_fat_g=per_serving_fat_g,
    )
```

**Mechanical integration steps:**
1. Add `MacrosRow` TypedDict definition above the function (before line 47).
2. Update `ScaledRecipe` TypedDict to include the 8 new fields (already shown above).
3. Replace the function body (lines 47–78) with the code above.
4. Run `pytest tests/unit/test_scaling.py` to verify backward compatibility.

---

## 9. Required Edits to `_get_recipe_with_ingredients()` in routes/recipes.py

**NOTE:** This is T-009's scope. T-007 defines the interface; T-009 implements the caller. This section documents the contract.

### Current state (lines 44–93)

The function currently:
1. Fetches `Recipe` row.
2. Fetches `RecipeIngredient` rows joined with `Ingredient`.
3. Builds list of `IngredientRow`.
4. Calls `scale_recipe(...)` with no `macros_lookup`.

### Required changes for T-009

The route handler must:

1. **Collect distinct `fdc_id`s** from ingredient rows (from `Ingredient.fdc_id`, which is nullable).
   ```python
   fdc_ids = {ing.fdc_id for ri, ing in rows if ing.fdc_id is not None}
   ```

2. **Query `UsdaFood` by `fdc_id`** (one SELECT with PK list).
   ```python
   if fdc_ids:
       usda_result = await session.execute(
           select(UsdaFood).where(UsdaFood.fdc_id.in_(fdc_ids))
       )
       usda_rows = usda_result.scalars().all()
   ```

3. **Build `macros_lookup: dict[ingredient_id, MacrosRow]`**.
   ```python
   macros_lookup: dict[int, MacrosRow] = {}
   for ri, ing in rows:
       if ing.fdc_id is not None:
           usda = next((u for u in usda_rows if u.fdc_id == ing.fdc_id), None)
           if usda:
               macros_lookup[ing.id] = MacrosRow(
                   kcal_per_100g=usda.kcal_per_100g,
                   protein_g_per_100g=usda.protein_g_per_100g,
                   carbs_g_per_100g=usda.carbs_g_per_100g,
                   fat_g_per_100g=usda.fat_g_per_100g,
               )
   ```

4. **Pass `macros_lookup` into `scale_recipe()`**.
   ```python
   scaled = scale_recipe(
       recipe_id=recipe.id,
       title=recipe.title,
       base_yield=recipe.base_yield,
       target_servings=servings,
       ingredients=ingredients,
       macros_lookup=macros_lookup if macros_lookup else None,  # Pass dict or None
   )
   ```

### Key detail: Key is `ingredient_id`, not `fdc_id`

- `macros_lookup` key = `Ingredient.id` (the recipe ingredient identifier).
- Value = `MacrosRow` (derived from `UsdaFood` row matched on `Ingredient.fdc_id`).
- This allows `scale_recipe()` to look up `macros_lookup[scaled_ing["ingredient_id"]]`.

**Why?** In `scaling.py`, we only have `ScaledIngredient` with `ingredient_id`. We don't have `fdc_id` in that context. The lookup must be keyed on what `scaling.py` can access.

### Performance note

- One extra query: `SELECT ... FROM usda_food WHERE fdc_id IN (...)` (PK index, ≤47 rows).
- One extra dict build: O(n) where n = # ingredients (≤47 typical).
- Net impact: negligible (sub-millisecond).

---

## 10. Test Cases for T-008 (Unit Tests)

T-008 must add the following 4 test cases to `tests/unit/test_scaling.py`. These are derived from PRP §3 D11 (gold-master test) and standard edge cases.

### Test 1: Veggie Omelette base_yield (macros available for all ingredients)

**Setup:**
- Use Veggie Omelette recipe (`recipe_id=2`, `base_yield=1`, 7 ingredients).
- Build `macros_lookup` with all 7 ingredients mapped (from PRP-USDA-MACROS-006 PoC).
- Call `scale_recipe(..., target_servings=1, macros_lookup=macros_lookup)`.

**Expected:**
- `scaled.total_kcal`, `total_protein_g`, `total_carbs_g`, `total_fat_g` are non-None floats.
- `per_serving_*` values match `total_* / 1`.
- Values match hand-calculated gold master (documented in test comment).

**Rationale:** Locks the math with a known-good recipe.

### Test 2: Veggie Omelette 2x scale (linear scaling)

**Setup:**
- Same recipe, `target_servings=2`.
- Same `macros_lookup`.

**Expected:**
- `scaled.total_kcal`, etc. are **exactly 2x** Test 1 totals.
- `per_serving_kcal = total_kcal / 2` (no rounding error).
- Validates that scaling is linear.

**Rationale:** Ensures per-serving division is correct.

### Test 3: Partial coverage (some ingredients missing from macros_lookup)

**Setup:**
- Use Overnight Oats recipe (5 ingredients, existing in fixtures).
- Build `macros_lookup` with only 3 of 5 ingredients mapped.
- Call `scale_recipe(..., macros_lookup=macros_lookup)`.

**Expected:**
- `scaled.total_kcal`, `total_protein_g`, `total_carbs_g`, `total_fat_g` are all `None`.
- `per_serving_*` are all `None`.
- Remaining fields (recipe_id, title, ingredients, total_grams) are populated normally.

**Rationale:** Tests PRP §3 D12 (coverage incomplete behavior).

### Test 4: No macros_lookup (backward compatibility)

**Setup:**
- Use any recipe.
- Call `scale_recipe(...)` with `macros_lookup=None` (or omit the kwarg).

**Expected:**
- All 8 new macro fields are `None`.
- Existing fields (recipe_id, title, scale_factor, ingredients, total_grams) unchanged.
- Return dict is valid `ScaledRecipe`.

**Rationale:** Ensures existing callers (no macros_lookup) still work without changes.

---

## 11. Summary of Changes

### Files modified by T-007

- **`app/services/scaling.py`** (lines 47–78: function body; +30 lines for new code)
  - Add `MacrosRow` TypedDict
  - Extend `ScaledRecipe` TypedDict with 8 new keys
  - Extend `scale_recipe()` signature with `macros_lookup` kwarg
  - Implement macros accumulation logic

### Files NOT modified by T-007 (owned by other tasks)

- `app/routes/recipes.py` → T-009 (wire macros_lookup into route handler)
- `app/templates/recipes/detail.html` → T-010 (display USDA macros block)
- `app/templates/recipes/ingredients.html` → T-011 (display macros tfoot)
- `tests/unit/test_scaling.py` → T-008 (add 4 unit tests)
- `fixtures/ingredient_fdc_mapping.json` → T-006, T-013 (ingredient-to-USDA mapping)
- `app/models/recipe.py` → T-003 (add nullable `fdc_id` FK to Ingredient)
- `app/models/usda_food.py` → T-002 (define UsdaFood model)
- `app/db/init_schema.py` → T-002 (register UsdaFood)

---

## 12. Verification Checklist

- [ ] Code sketch (§8) pastes and runs without syntax errors
- [ ] Backward compatibility test (§10 Test 4) passes
- [ ] Veggie Omelette gold-master test (§10 Test 1) passes with hand-verified totals
- [ ] Linear scaling test (§10 Test 2) confirms per-serving math
- [ ] Coverage-incomplete test (§10 Test 3) sets all 8 fields to None
- [ ] Existing unit tests in `test_scaling.py` still pass
- [ ] Return type `ScaledRecipe` includes all 8 new keys (linter check)
- [ ] No DB access in `scale_recipe()` — pure function guarantee holds
- [ ] Float precision: all intermediate sums use float, no rounding during accumulation

---

**END T-007 IMPLEMENTATION SPEC**
