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
from app.models import meal_plan as _meal_plan  # noqa: F401
from app.models import order as _order  # noqa: F401
from app.models import resident as _resident  # noqa: F401
from app.models.facility import Facility, FacilityType
from app.models.recipe import Ingredient, Recipe, RecipeIngredient
from app.models.user import User

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


def _seed_facilities(session: Session) -> int:
    """Load fixtures/facilities.json. Idempotent on Facility.name."""
    data = _load_json("facilities.json")
    added = 0
    for f in data:
        existing = session.exec(select(Facility).where(Facility.name == f["name"])).first()
        if existing is not None:
            continue
        row = Facility(
            id=f["id"],
            name=f["name"],
            type=FacilityType(f["type"]),
            bed_count=f["bed_count"],
            admin_email=f.get("admin_email"),
        )
        session.add(row)
        added += 1
    session.commit()
    return added


def _seed_admin_user_placeholder(session: Session) -> int:
    """Seed user id=1 as the admin placeholder bound to the facility with admin_email.

    `clerk_user_id` is a sentinel `__unprovisioned__` until the first real sign-in,
    at which point provisioning updates it. This satisfies FK constraints on demo
    orders (Slice C) that reference `placed_by_user_id=1`.
    """
    existing = session.exec(select(User).where(User.id == 1)).first()
    if existing is not None:
        return 0

    # Find the facility that has admin_email set (Phase 1 invariant: exactly one).
    facility = session.exec(select(Facility).where(Facility.admin_email.is_not(None))).first()
    if facility is None:
        return 0

    user = User(
        id=1,
        clerk_user_id="__unprovisioned__",
        email=facility.admin_email,
        facility_id=facility.id,
        role="admin",
    )
    session.add(user)
    session.commit()
    return 1


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
        f = _seed_facilities(session)
        u = _seed_admin_user_placeholder(session)
        r, i = _seed_recipes(session)

    print(
        f"Seeded: {f} facilities, {u} admin users, {r} recipes, "
        f"{i} recipe-ingredient links."
    )


if __name__ == "__main__":
    main()


# Phase 2 Graduation: move to Alembic data migrations.
