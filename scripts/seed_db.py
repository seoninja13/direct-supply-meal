"""
PSEUDOCODE:
1. Load fixtures/*.json and INSERT into the ds-meal SQLite DB.
2. Order: ingredients → recipes (+ RecipeIngredient joins) → facilities → residents (+ DietaryFlag joins) → demo orders (+ OrderLine + OrderStatusEvent histories).
3. Idempotent: if row already exists (by natural key) skip — supports re-running during dev.
4. Inputs: fixtures/recipes.json, fixtures/facilities.json, fixtures/residents.json, fixtures/demo_orders.json.
5. Outputs: populated SQLite at DATABASE_URL. Print a summary line.
6. Side effects: writes SQLite rows.

IMPLEMENTATION: Phase 4.

Sources: docs/workflows/DOMAIN-WORKFLOW.md §8 seed narrative.
"""

import json
from pathlib import Path

# from app.db.database import get_sync_session
# from app.models import (Facility, Recipe, Ingredient, RecipeIngredient, Resident, ...)


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# PSEUDO:
# - open sync session
# - for each fixture file: load JSON, dispatch to loader
# - print "Seeded: N facilities, M recipes, K residents, L demo orders"
def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()


# Phase 2 Graduation:
#   - Move to Alembic data migrations. Seam: scripts/migrations/.
