# Recipe Macro Verification (T-USDA-MACROS-014)

**Verified:** 2026-04-23
**Against:** commit `2b11e66` (tip of `main` after T-USDA-MACROS-013)
**Method:** async `scale_recipe()` call per recipe, values computed at `base_yield`, per-serving. Reseed of `/app/data/ds-meal.db` via `scripts/seed_db.py` (14,585 USDA rows loaded, 45/47 ingredients backfilled with `fdc_id`).

## Per-recipe results

| ID | Recipe | base_yield | Coverage | kcal | Protein (g) | Carbs (g) | Fat (g) | Verdict |
|----|--------|------------|----------|------|-------------|-----------|---------|---------|
| 1  | Chicken Stir-Fry               | 2 | 7/7 | 393.3  | 33.0 | 26.7 | 19.1 | OK |
| 2  | Veggie Omelette                | 1 | 6/7 | null   | null | null | null | FLAGGED (null by design: `salt and pepper` has no fdc_id per PRP D12 policy) |
| 3  | Overnight Oats                 | 4 | 5/5 | 365.1  |  9.7 | 61.0 | 10.6 | OK |
| 4  | Baked Cod + Rice               | 2 | 5/5 | 586.5  | 34.3 | 83.0 | 11.8 | OK |
| 5  | Beef Stew                      | 4 | 6/6 | 526.8  | 34.9 | 33.1 | 27.8 | OK |
| 6  | Pureed Chicken + Sweet Potato  | 2 | 4/4 | 352.7  | 28.9 | 32.6 | 12.0 | OK |
| 7  | Turkey Meatloaf                | 3 | 5/5 | 400.8  | 38.8 | 25.3 | 15.8 | OK |
| 8  | Lentil Soup                    | 4 | 6/6 | 314.4  | 20.2 | 57.9 |  1.4 | OK |
| 9  | Fruit & Yogurt Parfait         | 1 | 3/4 | null   | null | null | null | FLAGGED (null by design: `mixed berries` has no fdc_id; flagged for human review in T-013 notes) |
| 10 | Shepherd's Pie                 | 4 | 6/6 | 653.3  | 28.7 | 39.4 | 43.0 | OK |

### Sanity-band cross-check (recipes with computed macros)

| Recipe | Category | Expected band | Observed kcal | Verdict |
|--------|----------|---------------|---------------|---------|
| Chicken Stir-Fry              | Main course       | 300-900  |  393 | In band |
| Overnight Oats                | Light breakfast   | 200-500  |  365 | In band |
| Baked Cod + Rice              | Main course       | 300-900  |  587 | In band |
| Beef Stew                     | Main / heavy stew | 400-1200 |  527 | In band |
| Pureed Chicken + Sweet Potato | Main course       | 300-900  |  353 | In band |
| Turkey Meatloaf               | Main course       | 300-900  |  401 | In band |
| Lentil Soup                   | Soup (vegetarian) | 200-500  |  314 | In band |
| Shepherd's Pie                | Heavy casserole   | 400-1200 |  653 | In band |

All eight recipes with complete coverage land cleanly in the expected sanity band. Protein/carb/fat balances look plausible for each dish type (e.g., Lentil Soup — carb-forward and very low fat; Shepherd's Pie — high fat from meat + mash; Overnight Oats — carb-dominant).

## Flagged for human review

- **Recipe #2 Veggie Omelette** — `salt and pepper` (ingredient_id=13, 3g) has `fdc_id=null` by the T-013 mapping author's deliberate choice ("negligible macros — seasoning only contributes trace sodium"). Per PRP D12 policy, any null `fdc_id` triggers coverage-incomplete → the whole recipe reports null macros. The ~3g seasoning would contribute ~0 kcal if mapped to `Salt, table` (fdc=173468, 0 kcal/100g) + `Spices, pepper, black` (fdc=170931, 251 kcal/100g × ~1.5g = ~4 kcal total = 4 kcal per serving). A human reviewer should decide whether to:
  1. Accept the null (policy-correct per PRP D12), or
  2. Map `salt and pepper` to fdc=173468 (salt, zero-macro) to unlock the full rollup — the 4 kcal of pepper is below the sanity threshold and does not change the dish profile.

- **Recipe #9 Fruit & Yogurt Parfait** — `mixed berries` (ingredient_id=42, 150g) has `fdc_id=null` because USDA has no "mixed berries" entry. T-013 author explicitly flagged: "Parfait recipe (150g) contains unspecified berry blend. Macros will be approximated at 0; for production, replace with e.g. blueberries+strawberries split. Flagged for human review." 150g is a substantial portion of the parfait and a human must specify which berries are meant before this recipe can render macros.

## Fixes applied

- **None.** Both nulled recipes are null by the T-013 mapping author's deliberate design — not mapping errors — and correctly follow PRP D12 coverage-incomplete semantics. Per T-014 guardrail "Don't chase perfection" and the explicit policy note in `fixtures/ingredient_fdc_mapping.json` ("null fdc_id = negligible-macros seasoning"), both recipes are flagged for human review rather than mutated during verification.

## Summary

- **Total recipes:** 10
- **OK:** 8 (recipes 1, 3, 4, 5, 6, 7, 8, 10)
- **Borderline:** 0
- **Wrong:** 0
- **Fixed during T-014:** 0
- **Flagged for human review:** 2 (recipes 2, 9)

**No regressions detected.** `scale_recipe()` behaves exactly as specified by PRP D12: coverage-complete recipes return full macros; coverage-incomplete recipes return explicit nulls. T-013 mapping produces sensible per-serving numbers in the expected sanity bands for all 8 fully-covered recipes.
