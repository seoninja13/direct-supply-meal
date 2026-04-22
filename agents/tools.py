"""
agents/tools.py — pure async DB helpers (NO @tool decorators).

PSEUDOCODE (Phase 3 stub — no behavior).

These are the raw data-access primitives that the @tool wrappers in
tools_sdk.py compose. Every helper opens its own short-lived async SQLAlchemy
session — no session is shared across calls (per AGENT-WORKFLOW §5 rule).

Why separate from tools_sdk.py:
  - Unit-testable without the SDK runtime (no @tool decorator pollution).
  - Reusable from app/services/* when a FastAPI route needs the same lookup.
  - Keeps the @tool wrappers thin — they validate JSON schema + format
    tool_success/tool_error shapes, nothing else.

Functions provided:
  - db_get_recipe(recipe_id)
  - db_get_facility_residents(facility_id)
  - db_search_recipes(tags, exclude_allergens, max_cost_cents, texture_level)
  - db_check_ingredient_allergens(recipe_id, allergens)
  - db_insert_order(facility_id, recipe_id, n_servings, service_date, confirmed)
  - db_append_order_status_event(order_id, new_status, note, actor)
"""

from __future__ import annotations

import datetime as dt
from typing import Any

# Import models lazily to avoid circular-import + heavy startup.
# Actual session factory is provided by app.db (sibling package).


async def db_get_recipe(recipe_id: int) -> dict[str, Any] | None:
    """Fetch one recipe by primary key.

    Returns the recipe as a dict with canonical columns; None if not found.
    """
    # PSEUDO: 1. Open async session from app.db.get_session().
    # PSEUDO: 2. SELECT Recipe WHERE id = recipe_id.
    # PSEUDO: 3. If hit: build dict of {id, title, tags, texture_level, cost_cents_per_serving,
    # PSEUDO:    allergens, servings_default, ingredients_json}.
    # PSEUDO: 4. Close session. Return dict or None.
    raise NotImplementedError("Phase 3 stub — db_get_recipe not yet implemented")


async def db_get_facility_residents(facility_id: int) -> list[dict[str, Any]]:
    """Return the resident roster + dietary profiles for a facility.

    Used by check_compliance and the menu planner's census calculation.
    """
    # PSEUDO: 1. Open async session.
    # PSEUDO: 2. SELECT Resident JOIN DietaryProfile WHERE facility_id = ?.
    # PSEUDO: 3. Build list of {resident_id, dietary_flags[], allergens[], texture_level}.
    # PSEUDO: 4. Return list. Empty list for unknown facility is a valid answer.
    raise NotImplementedError("Phase 3 stub — db_get_facility_residents not yet implemented")


async def db_search_recipes(
    tags: list[str] | None = None,
    exclude_allergens: list[str] | None = None,
    max_cost_cents: int | None = None,
    texture_level: str | None = None,
) -> list[dict[str, Any]]:
    """Filter the recipe catalog. Empty filters = return all (capped).

    Filters are ANDed. Allergen exclusion intersects the Recipe.allergens column.
    """
    # PSEUDO: 1. Open async session.
    # PSEUDO: 2. Build query: SELECT Recipe WHERE (tags contain all of `tags`)
    # PSEUDO:    AND (allergens disjoint with exclude_allergens)
    # PSEUDO:    AND (cost_cents_per_serving <= max_cost_cents if given)
    # PSEUDO:    AND (texture_level <= texture_level if given).
    # PSEUDO: 3. LIMIT 50 (safety cap).
    # PSEUDO: 4. Serialize rows to dicts. Return list.
    raise NotImplementedError("Phase 3 stub — db_search_recipes not yet implemented")


async def db_check_ingredient_allergens(recipe_id: int, allergens: list[str]) -> dict[str, Any]:
    """Deterministic allergen intersection between a recipe and a disallow list.

    Returns {"clean": bool, "conflicts": list[str]}. Used by check_compliance.
    """
    # PSEUDO: 1. Load recipe via db_get_recipe.
    # PSEUDO: 2. If recipe is None → return {"clean": False, "conflicts": ["recipe_not_found"]}.
    # PSEUDO: 3. conflicts = set(recipe.allergens) & set(allergens).
    # PSEUDO: 4. Return {"clean": len(conflicts) == 0, "conflicts": sorted(list(conflicts))}.
    raise NotImplementedError("Phase 3 stub — db_check_ingredient_allergens not yet implemented")


async def db_insert_order(
    facility_id: int,
    recipe_id: int,
    n_servings: int,
    service_date: dt.date,
    confirmed: bool,
) -> dict[str, Any]:
    """Persist a new Order + OrderLine row; idempotent on (facility, recipe, service_date).

    Returns {"order_id": int, "status": "pending", "was_duplicate": bool}.
    """
    # PSEUDO: 1. Open async session, begin txn.
    # PSEUDO: 2. SELECT existing Order WHERE facility_id=? AND recipe_id=? AND service_date=?.
    # PSEUDO: 3. If found: return {"order_id": existing.id, "status": existing.status,
    # PSEUDO:    "was_duplicate": True}. (Do NOT bump qty silently — let the caller decide.)
    # PSEUDO: 4. Else: INSERT Order(status="pending"), INSERT OrderLine(recipe_id, n_servings),
    # PSEUDO:    call db_append_order_status_event(order_id, "pending", ...).
    # PSEUDO: 5. Commit. Return {"order_id": new.id, "status": "pending", "was_duplicate": False}.
    raise NotImplementedError("Phase 3 stub — db_insert_order not yet implemented")


async def db_append_order_status_event(
    order_id: int,
    new_status: str,
    note: str | None = None,
    actor: str | None = None,
) -> dict[str, Any]:
    """Write one row to OrderStatusEvent; enforce the pending→prepping→delivered state machine.

    Returns {"event_id": int, "from_status": str, "to_status": str}.
    Raises ValueError on invalid transition (caller turns into tool_error).
    """
    # PSEUDO: 1. Open async session.
    # PSEUDO: 2. SELECT latest OrderStatusEvent for order_id to find current status.
    # PSEUDO: 3. Validate (current → new_status) is in allowed transitions table:
    # PSEUDO:      pending → prepping, pending → cancelled,
    # PSEUDO:      prepping → delivered, prepping → cancelled,
    # PSEUDO:      delivered → <terminal>.
    # PSEUDO: 4. If invalid: raise ValueError("invalid_transition").
    # PSEUDO: 5. INSERT OrderStatusEvent(order_id, from_status, to_status=new_status, note, actor, ts=now).
    # PSEUDO: 6. UPDATE Order.status = new_status.
    # PSEUDO: 7. Commit. Return event dict.
    raise NotImplementedError("Phase 3 stub — db_append_order_status_event not yet implemented")


# Phase 2 Graduation: replace SQLite async session with Supabase Postgres async session
# once ds-meal promotes to the DuloCore prod pool. Seam is every function body's
# `get_session()` call — swap from app.db.sqlite to app.db.supabase. Signatures
# unchanged. Per DOMAIN-WORKFLOW database graduation path.
