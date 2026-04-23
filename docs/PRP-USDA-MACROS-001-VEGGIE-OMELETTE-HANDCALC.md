# Veggie Omelette — USDA Macros Hand-Calc (T-USDA-MACROS-006)

**PRP**: PRP-USDA-MACROS-001 (Phase B)
**Task**: T-USDA-MACROS-006 (PoC mapping)
**Recipe**: `fixtures/recipes.json` → id=2, "Veggie Omelette"
**Base yield**: 1 serving
**Source of mapping**: `fixtures/ingredient_fdc_mapping.json`
**Source of macros**: `usda_food` table (seeded from `fixtures/macro.csv`, 14,585 rows)

This document is the ground-truth hand-calc that PHASE-GATE-1 reviewers compare against
the scaling engine output (T-USDA-MACROS-007) for the Veggie Omelette recipe.

---

## Per-ingredient contribution at base_yield = 1

Formula per ingredient: `per-100g value × grams / 100`

| Ingredient | FDC ID | USDA description | Grams | kcal/100g | P/100g | C/100g | F/100g | kcal | Protein (g) | Carbs (g) | Fat (g) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| large eggs | 171287 | Egg, whole, raw, fresh | 100 | 143.000 | 12.560 | 0.720 | 9.510 | 143.000 | 12.560 | 0.720 | 9.510 |
| diced onion | 170000 | Onions, raw | 40 | 39.000 | 0.980 | 8.900 | 0.090 | 15.600 | 0.392 | 3.560 | 0.036 |
| diced tomato | 170457 | Tomatoes, red, ripe, raw, year round average | 50 | 18.000 | 0.880 | 3.890 | 0.200 | 9.000 | 0.440 | 1.945 | 0.100 |
| spinach leaves | 168462 | Spinach, raw | 20 | 25.000 | 2.855 | 3.020 | 0.505 | 5.000 | 0.571 | 0.604 | 0.101 |
| olive oil | 171413 | Oil, olive, salad or cooking | 15 | 884.000 | 0.000 | 0.000 | 100.000 | 132.600 | 0.000 | 0.000 | 15.000 |
| small corn tortillas | 2343303 | Tortilla, corn | 150 | 218.000 | 5.700 | 44.640 | 2.850 | 327.000 | 8.550 | 66.960 | 4.275 |
| salt and pepper | null | (seasoning — negligible macros) | 3 | — | — | — | — | 0.000 | 0.000 | 0.000 | 0.000 |
| **TOTAL (base_yield = 1)** | | | **378** | | | | | **632.200** | **22.513** | **73.789** | **29.022** |
| **PER SERVING** | | | | | | | | **632.2** | **22.51** | **73.79** | **29.02** |

Because `base_yield = 1`, the total and per-serving rows are identical. The per-serving column
is the value the compliance engine and the recipe detail page will render.

---

## Sanity check

A "textbook" 2-egg veggie omelette served plain is ~220-280 kcal. This recipe's per-serving
value is **~632 kcal**, which falls *outside* the naive 250-400 kcal range suggested by the
task guardrail.

**Root cause**: the recipe bundles **150 g of corn tortillas** (≈ 327 kcal, ≈ 52% of the plate)
and **15 g of olive oil** (≈ 133 kcal, ≈ 21% of the plate) with the omelette base. The
"omelette" itself (eggs + veg) is ~170 kcal. Effectively this is an omelette + tortilla plate,
not a bare omelette.

**Conclusions**:

1. **The hand-calc is arithmetically correct** — every row reconciles against per-100g × grams / 100.
2. **The USDA mappings are the correct raw-default picks** — the larger-than-expected total is
   driven by the recipe composition (tortillas + oil), not by the FDC choices.
3. **Protein (22.5 g), carbs (73.8 g), and fat (29.0 g)** are consistent with an
   egg + tortilla + oil plate and do not indicate any unit-of-measure bug (e.g. mistaking
   kJ for kcal, or `per-gram` for `per-100g`).
4. **`carbs_g`** from `recipes.json` is hardcoded at **22 g** for this recipe, but the USDA-derived
   total is **73.8 g**. This 51 g discrepancy is expected and is exactly why PRP-USDA-MACROS-001
   is migrating the compliance engine off the hardcoded `Recipe.carbs_g` column onto
   USDA-derived totals (§3 D1 / Phase 2 Graduation note in `app/models/usda_food.py`). The
   PoC-mapping task is the first step in that migration; this discrepancy confirms the
   migration is necessary.

---

## Null-coverage note (PRP D12)

`salt and pepper` is intentionally mapped to `fdc_id: null`. Per PRP D12, a null fdc_id
triggers a **coverage-incomplete None response** only when the ingredient's true macro
contribution is unknown. Salt and pepper legitimately contribute ~0 kcal / 0 g protein /
0 g carbs / 0 g fat, so excluding them from totals is correct and the coverage-incomplete
path should treat `salt and pepper` as a **known-zero** exemption rather than a
missing-data block. Implementation guidance for `app/services/scaling.py` (T-USDA-MACROS-007):
a curated "known-zero seasoning" allow-list lets recipes with only seasoning-nulls still
return a full macro total.

---

## Reproduction

```python
# Run via /opt/direct-supply-meal/.venv/bin/python from repo root.
from sqlmodel import Session, create_engine
from app.models.usda_food import UsdaFood

e = create_engine("sqlite:////app/data/ds-meal.db")
s = Session(e)

mapping = [
    ("large eggs",           100, 171287),
    ("diced onion",           40, 170000),
    ("diced tomato",          50, 170457),
    ("spinach leaves",        20, 168462),
    ("olive oil",             15, 171413),
    ("small corn tortillas", 150, 2343303),
    ("salt and pepper",        3, None),
]
total = {"kcal": 0.0, "p": 0.0, "c": 0.0, "f": 0.0}
for name, grams, fdc in mapping:
    if fdc is None:
        continue
    r = s.get(UsdaFood, fdc)
    total["kcal"] += r.kcal_per_100g      * grams / 100
    total["p"]    += r.protein_g_per_100g * grams / 100
    total["c"]    += r.carbs_g_per_100g   * grams / 100
    total["f"]    += r.fat_g_per_100g     * grams / 100
print(total)
# -> {'kcal': 632.2, 'p': 22.513, 'c': 73.789, 'f': 29.022}
```
