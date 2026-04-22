"""
PSEUDOCODE:
1. One-line summary of module purpose.
   - Resident SQLModel, DietaryFlag enum, and the ResidentDietaryFlag join table per Section 2.
2. Ordered steps.
   a. Declare DietaryFlag enum — 11 flags used by the compliance engine (Section 5).
   b. Declare Resident SQLModel (id, facility_id FK, demographics JSON).
   c. Declare ResidentDietaryFlag join (resident_id FK + flag enum value).
   d. Compliance aggregator reads flags via a JOIN against ResidentDietaryFlag.
3. Inputs / Outputs.
   - Inputs: seed fixtures (Section 8) + future admin CRUD (Phase 2).
   - Outputs: Resident rows consumed by compliance.check_compliance() roll-ups for facility menus.
4. Side effects.
   - None. Table definitions only.

IMPLEMENTATION: Phase 4 — see functions below.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class DietaryFlag(str, Enum):
    # PSEUDO: Canonical dietary flags per DOMAIN-WORKFLOW Section 5.
    #   - diabetic: triggers carbs_g rule.
    #   - low_sodium: triggers sodium_mg rule.
    #   - renal: triggers potassium + phosphorus rules.
    #   - soft_food / pureed / mechanical_soft: texture_level constraints.
    #   - allergen_*: intersect recipe.allergens to produce hard fails.
    DIABETIC = "diabetic"
    LOW_SODIUM = "low_sodium"
    RENAL = "renal"
    SOFT_FOOD = "soft_food"
    PUREED = "pureed"
    MECHANICAL_SOFT = "mechanical_soft"
    ALLERGEN_NUTS = "allergen_nuts"
    ALLERGEN_DAIRY = "allergen_dairy"
    ALLERGEN_GLUTEN = "allergen_gluten"
    ALLERGEN_SHELLFISH = "allergen_shellfish"
    ALLERGEN_EGG = "allergen_egg"


class Resident(SQLModel, table=True):
    # PSEUDO: Resident table — the individual a MealPlan must honor.
    #   - id: PK.
    #   - facility_id: FK to facility.id.
    #   - demographics: JSON bag (age, room_number, max_carbs_per_meal override, free-form notes).
    #     Phase 1 leaves demographics free-form so seed data can evolve without schema churn.
    __tablename__ = "resident"

    id: int | None = Field(default=None, primary_key=True)
    facility_id: int = Field(foreign_key="facility.id", index=True)
    demographics: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class ResidentDietaryFlag(SQLModel, table=True):
    # PSEUDO: Join table between Resident and DietaryFlag.
    #   - id: PK (synthetic).
    #   - resident_id: FK to resident.id (indexed; primary access path).
    #   - flag: DietaryFlag enum value stored as string.
    #   - Phase 1 leaves the (resident_id, flag) uniqueness as an application-level concern; seed
    #     data is generated and known-unique. Phase 2 will add a composite unique constraint.
    __tablename__ = "resident_dietary_flag"

    id: int | None = Field(default=None, primary_key=True)
    resident_id: int = Field(foreign_key="resident.id", index=True)
    flag: DietaryFlag


# Phase 2 Graduation: promote demographics JSON blob to first-class columns (age, room, caregiver)
# once the shape stabilizes; add composite UNIQUE(resident_id, flag); add user-tunable caps per flag.
