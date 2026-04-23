"""
PSEUDOCODE:
1. One-line summary of module purpose.
   - UsdaFood SQLModel table for USDA macronutrient lookup (per PRP-USDA-MACROS-001 §3 D1).
2. Ordered steps.
   a. Declare UsdaFood with fdc_id PK (int) + description + four per-100g macro columns
      (kcal, protein_g, carbs_g, fat_g) sourced from fixtures/macro.csv.
   b. Keep the table standalone — Ingredient gets a nullable fdc_id FK in T-USDA-MACROS-003.
3. Inputs / Outputs.
   - Inputs: fixtures/macro.csv (14,585 rows) loaded by scripts/seed_usda.py (T-USDA-MACROS-004).
   - Outputs: rows consumed at render time by app/services/scaling.py (T-USDA-MACROS-007)
     to produce per-recipe macro totals.
4. Side effects.
   - None. Table definition only.

IMPLEMENTATION: Phase A (T-USDA-MACROS-002) — see class below.
"""

from __future__ import annotations

from sqlmodel import Field, SQLModel


class UsdaFood(SQLModel, table=True):
    # PSEUDO: UsdaFood table — per-100g macronutrient reference.
    #   - fdc_id: USDA FoodData Central ID (PK, not auto-generated — sourced from macro.csv).
    #   - description: human-readable USDA description (e.g. "Chicken, broilers or fryers, breast, raw").
    #   - kcal_per_100g: calories per 100g (float; USDA ships 2-decimal precision).
    #   - protein_g_per_100g: grams of protein per 100g.
    #   - carbs_g_per_100g: grams of carbohydrates per 100g.
    #   - fat_g_per_100g: grams of fat per 100g.
    __tablename__ = "usda_food"

    fdc_id: int = Field(primary_key=True)
    description: str
    kcal_per_100g: float
    protein_g_per_100g: float
    carbs_g_per_100g: float
    fat_g_per_100g: float


# Phase 2 Graduation: add micronutrients (sodium/potassium/phosphorus) once the compliance engine is
# migrated off hardcoded Recipe columns onto USDA-derived totals.
