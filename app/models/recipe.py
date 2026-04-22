"""
PSEUDOCODE:
1. One-line summary of module purpose.
   - Recipe + Ingredient + RecipeIngredient SQLModel tables per DOMAIN-WORKFLOW Section 2/5.
2. Ordered steps.
   a. Declare Recipe with nutrition columns used by the compliance engine (carbs/sodium/K/P).
   b. Declare Ingredient with allergen_tags JSON + unit_cost_cents for static pricing rollup.
   c. Declare RecipeIngredient join with grams (scaled by scale_recipe()).
   d. allergens/allergen_tags stored as JSON arrays (list[str]) — intersected in compliance rules.
3. Inputs / Outputs.
   - Inputs: seed fixtures (10 recipes per Section 8) + future admin CRUD.
   - Outputs: Recipe + Ingredient rows consumed by pricing, compliance, scaling, meal plan, order.
4. Side effects.
   - None. Table definitions only.

IMPLEMENTATION: Phase 4 — see functions below.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class Recipe(SQLModel, table=True):
    # PSEUDO: Recipe table.
    #   - id: PK.
    #   - title: display name.
    #   - texture_level: 0 (pureed) .. 4 (regular) per Section 5 rules.
    #   - allergens: JSON list[str] (e.g. ["nuts", "dairy"]) intersected with resident allergen flags.
    #   - cost_cents_per_serving: static baseline used by /recipes and by estimate_cost fallback.
    #   - prep_time_minutes: advisory field for kitchen planning.
    #   - base_yield: default servings for static_rollup when n_servings omitted.
    #   - carbs_g / sodium_mg / potassium_mg / phosphorus_mg: nutrition columns consumed by the
    #     compliance rule functions (diabetic, low_sodium, renal).
    __tablename__ = "recipe"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    texture_level: int = Field(ge=0, le=4)
    allergens: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    cost_cents_per_serving: int
    prep_time_minutes: int
    base_yield: int
    carbs_g: int
    sodium_mg: int
    potassium_mg: int
    phosphorus_mg: int


class Ingredient(SQLModel, table=True):
    # PSEUDO: Ingredient table.
    #   - id: PK.
    #   - name: ingredient name ("chicken breast", "white rice").
    #   - allergen_tags: JSON list[str] rolled up into recipe.allergens at seed time.
    #   - unit_cost_cents: cost per gram (int cents). Feeds Phase 2 supplier ERP seam.
    __tablename__ = "ingredient"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    allergen_tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    unit_cost_cents: int


class RecipeIngredient(SQLModel, table=True):
    # PSEUDO: Join table — recipe composition.
    #   - id: synthetic PK.
    #   - recipe_id: FK to recipe.id (indexed).
    #   - ingredient_id: FK to ingredient.id (indexed).
    #   - grams: integer grams in base_yield — multiplied by (target/base_yield) in scaling.py.
    __tablename__ = "recipe_ingredient"

    id: Optional[int] = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="recipe.id", index=True)
    ingredient_id: int = Field(foreign_key="ingredient.id", index=True)
    grams: int


# Phase 2 Graduation: replace the allergens JSON column with a real many-to-many Allergen table once
# admin UI for ingredient CRUD ships; add recipe versioning (effective_from / effective_to) and a
# unit-conversion table once supplier ERP data replaces seed fixtures.
