# direct-supply-meal — Current State

**Last updated:** 2026-04-23 by Director-ARCH (parallel task orchestration)
**Branch on main:** 2ff4265fea1e4c3557e5e92891aca219bc6b9767
**Live environment:** ds-meal.dulocore.com (Phase 1 shipped)

## Shipped features (stable on main)
- Recipe catalog (public): /recipes, /recipes/{id}, /recipes/{id}/ingredients + JSON twins
- Scaling service: pure function, gram-based, integer servings
- Facility dashboard + meal plans + orders + calendar (auth-gated)
- Menu Planner agent (Sonnet) + NL Ordering agent (Haiku)
- Clerk auth with Google OAuth
- SQLite + SQLModel + aiosqlite
- Full test suite: unit + integration + Playwright E2E

## In progress — USDA Macros feature (PRP-USDA-MACROS-001)

**Approved:** 2026-04-23 by Ivan
**Progress:** 15/18 tasks complete. Only T-016 + T-017 remain (verification harness + ship).

### End-to-end working on main (commit 2ff4265)

- ✅ USDA FoodData Central loaded: 14,585 rows via idempotent `scripts/seed_usda.py`
- ✅ `UsdaFood` SQLModel + nullable `fdc_id` FK on `Ingredient`
- ✅ 45/47 ingredients mapped to USDA entries (2 intentional nulls: `salt and pepper`, `mixed berries`)
- ✅ `seed_db.py` backfills `Ingredient.fdc_id` from `fixtures/ingredient_fdc_mapping.json`
- ✅ `scale_recipe()` computes per-ingredient macros, sums, returns 8 macro fields
- ✅ Routes wired: `_get_recipe_with_ingredients` builds `macros_lookup` per request
- ✅ HTML: `/recipes/{id}` shows "USDA macros (per serving)" section (anonymous, no auth needed)
- ✅ HTML: `/recipes/{id}/ingredients` shows tfoot total + per-serving paragraph
- ✅ JSON API: `/api/v1/recipes/*` returns 8 macro fields when coverage complete
- ✅ None-safe: any null fdc_id → "macros unavailable" badge, no runtime error
- ✅ Unit tests: 9/9 scaling tests pass (2 gold-master tests lock in Veggie Omelette = 632.2 kcal)
- ✅ Integration tests: 46/46 pass (includes new test asserting sanity range 300–1000 kcal for recipe 2)
- ✅ E2E Playwright tests: 3 tests written (skip against live until deploy catches up)

### Tasks done
| # | Task | Commit |
|---|------|--------|
| T-001 | Vendor macro.csv (14,585 rows) | db1304d |
| T-002 | UsdaFood SQLModel | c2169c8 |
| T-003 | fdc_id FK on Ingredient | 4fac54b |
| T-004 | seed_usda.py idempotent loader | 1a98df6 |
| T-005 | Candidate mapping JSON (fuzzy top-3) | 1b06558 |
| T-006 | PoC mapping: Veggie Omelette | dc535eb |
| PHASE-GATE-1 | Ivan approval | (gate passed) |
| T-007 | scale_recipe math | 8f83d03 |
| T-008 | Gold-master unit tests | 8f83d03 |
| T-009 | Route handler macros_lookup wiring | 4e927d8 |
| T-010 | detail.html USDA macros section | 24bc44e |
| T-011 | ingredients.html tfoot + paragraph | 24bc44e |
| T-012 | JSON API integration test | 24bc44e |
| T-013 | Finalize 40 remaining mappings + seed_db backfill | 2b11e66 |
| T-014 | Verify 10 recipes render sensible macros | 011c6a8 |
| T-015 | E2E Playwright test | 2ff4265 |

### Remaining
- **T-016** pre-merge verification harness (full lint + test + type-check run; create VERIFICATION-RESULTS.md)
- **T-017** ship — flip CATALOG row `IN-PROGRESS` → `SHIPPED`, update DEMO-SCRIPT.md, delete Appendix A staging from PRP

### Known issues / caveats
- **Recipe 2 (Veggie Omelette)** + **Recipe 9 (Fruit & Yogurt Parfait)** show "macros unavailable" on live pages because the rollup is all-or-nothing (PRP D12): a single null fdc_id → entire recipe returns None on all 8 fields. Both have intentional null ingredients (`salt and pepper`, `mixed berries`). Fix = map `salt and pepper` to `Salt, table` (fdc=173468, zero-kcal) and split `mixed berries` into named berries. Captured in T-014 verification report.
- **Deploy pending** — main is ahead of `ds-meal.dulocore.com`. Docker rebuild must run from the local Windows machine (VPS rebuild is blocked). Feature won't be browser-visible until rebuild.
- **mypy pre-existing errors** on `app/routes/recipes.py` (join arg type + `recipe.id` optional). Not introduced by this PRP; tracked separately.
- **8 of 10 recipes** render clean numeric macros on /recipes/{id} once deployed.

## Deployment
- dev.dulocore.com — DuloCore main project
- ds-meal.dulocore.com — this app (Phase 1 shipped, USDA macros NOT yet deployed)

## Key links
- [PRP-USDA-MACROS-001](PRP-USDA-MACROS-001.md)
- [T-014 verification report](PRP-USDA-MACROS-001-RECIPE-VERIFICATION.md)
- [Phase D diffs](PRP-USDA-MACROS-001-PHASE-D-DIFFS.md)
- [Veggie Omelette hand-calc](PRP-USDA-MACROS-001-VEGGIE-OMELETTE-HANDCALC.md)
- [GitHub repo](https://github.com/seoninja13/direct-supply-meal)
