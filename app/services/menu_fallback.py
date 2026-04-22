"""
PSEUDOCODE:
1. Purpose: Deterministic menu generator used when the Menu Planner
   LLM is unavailable (missing key, revoked, rate-limited). Per
   AGENT-WORKFLOW.md Section 8, the route NEVER crashes — it falls
   back to this pure-Python picker and persists with
   pricing_mode = "static_fallback" and a visible UI badge.
2. Ordered algorithm:
   a. Load Facility(facility_id) + its Residents + each resident's
      dietary_flags to form a census profile:
        facility_allergens   = union of all resident.allergen_flags
        facility_texture_max = min of required texture levels
                               (soft_food => 2, pureed => 1, else 4)
        bed_count            = facility.bed_count
   b. SELECT Recipes ORDER BY cost_cents_per_serving ASC.
   c. Deterministically filter:
         drop recipe if any of its allergens
           intersects facility_allergens
         drop recipe if recipe.texture_level > facility_texture_max
   d. If after filtering fewer than some minimum remain,
      raise FallbackUnsatisfiable — route surfaces an error banner.
   e. Fill 21 slots (7 days x 3 meals) round-robin over the
      filtered recipes. Stable ordering => reproducible menu.
      Servings per slot = bed_count.
   f. Persist MealPlan(week_start=week_start,
                       facility_id=facility_id,
                       created_by_user_id=SYSTEM_USER,
                       pricing_mode="static_fallback")
      with 21 MealPlanSlot rows.
   g. Return the MealPlan.
3. Inputs / Outputs:
   - Inputs: facility_id:int, week_start:date.
   - Output: MealPlan row (with slots).
4. Side effects: One write transaction (MealPlan + 21 MealPlanSlot
   rows). Zero LLM calls. Idempotent-by-design: same (facility_id,
   week_start, recipe catalog) -> same slot sequence.

IMPLEMENTATION: Phase 4.
"""

from __future__ import annotations

from datetime import date
from typing import Any

MEALS_PER_DAY: int = 3          # breakfast, lunch, dinner
DAYS_PER_WEEK: int = 7
SLOTS_PER_WEEK: int = DAYS_PER_WEEK * MEALS_PER_DAY   # 21
MEAL_TYPES: tuple[str, str, str] = ("breakfast", "lunch", "dinner")
MIN_RECIPES_REQUIRED: int = 3
SYSTEM_USER_ID: int = 0         # sentinel — seeded in scripts/seed_db.py


class FallbackUnsatisfiable(Exception):
    """Fewer than MIN_RECIPES_REQUIRED recipes survive the filter."""


def _facility_profile(facility_id: int) -> dict:
    # PSEUDO:
    #   facility  = load Facility(facility_id)              # app.models.facility
    #   residents = load Resident.where(facility_id) with
    #               .dietary_flags + .allergen_flags eager
    #   allergens = set()
    #   tex_caps  = [4]
    #   for r in residents:
    #       allergens |= set(r.allergen_flags or [])
    #       for f in r.dietary_flags:
    #           if f.flag == "soft_food": tex_caps.append(2)
    #           elif f.flag == "pureed":  tex_caps.append(1)
    #   return {"facility": facility,
    #           "allergens": allergens,
    #           "texture_max": min(tex_caps),
    #           "bed_count": facility.bed_count}
    raise NotImplementedError("Phase 4")


def _filter_recipes(recipes: list[Any], profile: dict) -> list[Any]:
    # PSEUDO:
    #   keep = []
    #   for r in recipes:                          # already cost-ASC sorted
    #       if set(r.allergens or []) & profile["allergens"]:
    #           continue
    #       if r.texture_level > profile["texture_max"]:
    #           continue
    #       keep.append(r)
    #   return keep
    raise NotImplementedError("Phase 4")


def generate_fallback_menu(facility_id: int, week_start: date) -> Any:
    # PSEUDO:
    #   1. profile = _facility_profile(facility_id)
    #   2. all_recipes = SELECT Recipe ORDER BY cost_cents_per_serving ASC
    #   3. eligible  = _filter_recipes(all_recipes, profile)
    #      if len(eligible) < MIN_RECIPES_REQUIRED:
    #          raise FallbackUnsatisfiable(facility_id)
    #   4. plan = MealPlan(
    #        facility_id=facility_id,
    #        week_start=week_start,
    #        created_by_user_id=SYSTEM_USER_ID,
    #        pricing_mode="static_fallback",
    #      )
    #      db.add(plan); db.flush()
    #   5. for i in range(SLOTS_PER_WEEK):
    #          day      = i // MEALS_PER_DAY            # 0..6
    #          meal_idx = i %  MEALS_PER_DAY            # 0..2
    #          recipe   = eligible[i % len(eligible)]   # round-robin
    #          db.add(MealPlanSlot(
    #              meal_plan_id=plan.id,
    #              day_of_week=day,
    #              meal_type=MEAL_TYPES[meal_idx],
    #              recipe_id=recipe.id,
    #              n_servings=profile["bed_count"],
    #          ))
    #   6. db.commit()
    #   7. return plan
    raise NotImplementedError("Phase 4")


# Phase 2 Graduation: services/menu_fallback.py::generate_fallback_menu()
# — swap round-robin picker for an ILP that minimizes cost subject to
# census-level dietary mix and repeat-meal penalties; same function
# signature so the Menu Planner fallback path stays unchanged.
