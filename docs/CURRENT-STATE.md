# direct-supply-meal — Current State

**Last updated:** 2026-04-23 by Director-ARCH (parallel task orchestration)
**Branch on main:** f66c1575c82de6ce4a587c5496c668162f0ec809
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
**Progress:** 6/17 tasks complete + 1 phase gate pending

### Done
- T-001 vendor macro.csv (14,585 rows)
- T-002 UsdaFood SQLModel
- T-003 fdc_id FK on Ingredient
- T-004 seed_usda.py (idempotent)
- T-005 candidate mapping JSON (47 ingredients, top-3 each)
- T-006 PoC mapping: Veggie Omelette (7 ingredients)
- T-007/008 scaffold: signature + None-path + test scaffolds
- T-017 prep: CATALOG row + DEMO-SCRIPT blurb pre-staged
- Phase D prep: copy-paste diffs for T-010/011/012

### Blocking: PHASE-GATE-1 — Ivan reviews PoC mapping
- Hand-calc: 632 kcal/serving (Veggie Omelette). Needs approval before T-007 math fill-in.
- File to review: fixtures/ingredient_fdc_mapping.json
- Hand-calc doc: docs/PRP-USDA-MACROS-001-VEGGIE-OMELETTE-HANDCALC.md

### Blocked on gate
- T-007 math fill-in (summation loop)
- T-008 gold-master assertions
- T-009 route handler wiring
- T-010/011/012 templates + JSON API
- T-013 finalize remaining 40 ingredient mappings
- T-014/015 reseed + E2E
- T-016/017 verification + ship

## Known issues / risks
- Fuzzy matching mis-picked ~30/47 top-1 candidates (workers bypassed via direct DB query for the PoC). T-013 will be human-curated.
- Veggie Omelette hand-calc shows 327 kcal/serving from corn tortillas alone (150g). May indicate fixture overcounts tortilla weight — worth Ivan's eye at gate review.
- Shared worktree contention observed between parallel agents — recovered cleanly but a risk for larger parallel waves.

## Deployment
- dev.dulocore.com — DuloCore main project
- ds-meal.dulocore.com — this app (Phase 1 shipped, USDA macros NOT yet deployed)

## Key links
- [PRP-USDA-MACROS-001](docs/PRP-USDA-MACROS-001.md)
- [Phase D diffs](docs/PRP-USDA-MACROS-001-PHASE-D-DIFFS.md)
- [Veggie Omelette hand-calc](docs/PRP-USDA-MACROS-001-VEGGIE-OMELETTE-HANDCALC.md)
- [GitHub repo](https://github.com/seoninja13/direct-supply-meal)
