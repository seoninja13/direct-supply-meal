"""
PSEUDOCODE:
1. Load fixtures/*.json and INSERT into SQLite. Slice A scope: recipes + ingredients + RecipeIngredient.
2. Idempotent on natural keys (recipe.title, ingredient.name, (recipe_id, ingredient_id)).
3. Slice B/C will extend to facilities, residents, users, demo orders.

IMPLEMENTATION: Slice A.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select

from app.db.database import _sync_url
from app.db.init_schema import (
    AgentTrace,  # noqa: F401
    init_schema,  # noqa: F401 — registers tables
)

# Ensure SQLModel.metadata sees every table before create_all.
from app.models import facility as _facility  # noqa: F401
from app.models import meal_plan as _meal_plan  # noqa: F401
from app.models import order as _order  # noqa: F401
from app.models import resident as _resident  # noqa: F401
from app.models import user as _user  # noqa: F401
from app.models.recipe import Ingredient, Recipe, RecipeIngredient

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load_json(name: str) -> Any:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _get_or_create_ingredient(session: Session, name: str, allergen_tags: list[str]) -> int:
    existing = session.exec(select(Ingredient).where(Ingredient.name == name)).first()
    if existing is not None:
        return existing.id
    row = Ingredient(name=name, allergen_tags=list(allergen_tags), unit_cost_cents=0)
    session.add(row)
    session.flush()
    return row.id


def _seed_recipes(session: Session) -> tuple[int, int]:
    recipes_data = _load_json("recipes.json")
    recipe_count = 0
    ingredient_count = 0

    for r in recipes_data:
        # Idempotent on title.
        existing = session.exec(select(Recipe).where(Recipe.title == r["title"])).first()
        if existing is not None:
            continue

        recipe = Recipe(
            id=r["id"],
            title=r["title"],
            texture_level=r["texture_level"],
            allergens=list(r.get("allergens", [])),
            cost_cents_per_serving=r["cost_cents_per_serving"],
            prep_time_minutes=r["prep_time_minutes"],
            base_yield=r["base_yield"],
            carbs_g=r["carbs_g"],
            sodium_mg=r["sodium_mg"],
            potassium_mg=r["potassium_mg"],
            phosphorus_mg=r["phosphorus_mg"],
        )
        session.add(recipe)
        session.flush()
        recipe_count += 1

        for ing in r["ingredients"]:
            ingredient_id = _get_or_create_ingredient(
                session, ing["name"], ing.get("allergen_tags", [])
            )
            ingredient_count += 1
            session.add(
                RecipeIngredient(
                    recipe_id=recipe.id,
                    ingredient_id=ingredient_id,
                    grams=int(ing["grams"]),
                )
            )
        session.flush()

    session.commit()
    return recipe_count, ingredient_count


def main() -> None:
    # Use a SYNC engine for the script; app runtime uses the async engine.
    engine = create_engine(_sync_url(), future=True)

    # Ensure parent dir for SQLite file.
    url = str(engine.url)
    if url.startswith("sqlite:////"):
        db_path = Path("/" + url.split("sqlite:////", 1)[1])
        db_path.parent.mkdir(parents=True, exist_ok=True)
    elif url.startswith("sqlite:///"):
        db_path = Path(url.split("sqlite:///", 1)[1])
        db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create tables (idempotent).
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        r, i = _seed_recipes(session)

    print(f"Seeded: {r} recipes, {i} recipe-ingredient links.")


if __name__ == "__main__":
    main()


# Phase 2 Graduation: move to Alembic data migrations.
