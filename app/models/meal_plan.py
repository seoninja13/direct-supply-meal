"""
PSEUDOCODE:
1. One-line summary of module purpose.
   - MealPlan + MealPlanSlot SQLModel tables — output of the Menu Planner agent (J3).
2. Ordered steps.
   a. Declare MealPlan (id, facility_id, week_start, created_by_user_id).
   b. Declare MealType enum (breakfast | lunch | dinner).
   c. Declare MealPlanSlot (meal_plan_id, day_of_week 0-6, meal_type, recipe_id, n_servings).
   d. Post-save hook in services/orders.py converts slots into daily Orders (see Section 9 seam).
3. Inputs / Outputs.
   - Inputs: LLM-generated plan + user confirmation from /meal-plans/new.
   - Outputs: up to 21 slot rows per plan (7 days × 3 meals) consumed by generate_from_meal_plan().
4. Side effects.
   - None at model level.

IMPLEMENTATION: Phase 4 — see functions below.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class MealType(str, Enum):
    # PSEUDO: Three meal slots per day — canonical labels used by the UI grid and order generator.
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"


class MealPlan(SQLModel, table=True):
    # PSEUDO: MealPlan table — a weekly menu owned by a facility.
    #   - id: PK.
    #   - facility_id: FK to facility.id.
    #   - week_start: date (Monday of the target week).
    #   - created_by_user_id: FK to user.id (dietitian or admin who ran Menu Planner).
    __tablename__ = "meal_plan"

    id: Optional[int] = Field(default=None, primary_key=True)
    facility_id: int = Field(foreign_key="facility.id", index=True)
    week_start: date = Field(index=True)
    created_by_user_id: int = Field(foreign_key="user.id", index=True)


class MealPlanSlot(SQLModel, table=True):
    # PSEUDO: MealPlanSlot table — one recipe assigned to one (day, meal) cell of a MealPlan.
    #   - id: synthetic PK.
    #   - meal_plan_id: FK to meal_plan.id (indexed).
    #   - day_of_week: 0 (Monday) .. 6 (Sunday) per ISO convention.
    #   - meal_type: MealType enum value.
    #   - recipe_id: FK to recipe.id.
    #   - n_servings: how many servings this slot covers (typically facility-wide headcount).
    __tablename__ = "meal_plan_slot"

    id: Optional[int] = Field(default=None, primary_key=True)
    meal_plan_id: int = Field(foreign_key="meal_plan.id", index=True)
    day_of_week: int = Field(ge=0, le=6)
    meal_type: MealType
    recipe_id: int = Field(foreign_key="recipe.id", index=True)
    n_servings: int


# Phase 2 Graduation: add per-slot override for compliance exceptions (e.g. "renal variant for room
# 214"); promote day_of_week+meal_type to a composite UNIQUE once the generator is idempotent; add
# plan_status (draft/published/archived) so Menu Planner can save WIPs.
