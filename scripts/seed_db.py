"""
Seed fixtures/*.json into SQLite. Slices A→C scope:

- Slice A: recipes + ingredients + RecipeIngredient.
- Slice B: facilities + admin user placeholder.
- Slice C: residents + ResidentDietaryFlag + 5 demo orders with timelines.

Idempotent on natural keys (recipe.title, ingredient.name, facility.name,
order.id, resident.id). Safe to re-run.
"""

from __future__ import annotations

import json
from datetime import date, datetime
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
from app.models.facility import Facility, FacilityType
from app.models.order import (
    Order,
    OrderLine,
    OrderStatus,
    OrderStatusEvent,
    PricingSource,
)
from app.models.recipe import Ingredient, Recipe, RecipeIngredient
from app.models.resident import DietaryFlag, Resident, ResidentDietaryFlag
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


def _seed_residents(session: Session) -> tuple[int, int]:
    """Load fixtures/residents.json. Idempotent on Resident.id.

    Returns (residents_inserted, dietary_flag_rows_inserted).
    """
    path = FIXTURES_DIR / "residents.json"
    if not path.exists():
        return (0, 0)
    data = _load_json("residents.json")

    r_added = 0
    f_added = 0
    for r in data:
        existing = session.exec(select(Resident).where(Resident.id == r["id"])).first()
        if existing is not None:
            continue
        session.add(
            Resident(
                id=r["id"],
                facility_id=r["facility_id"],
                demographics=dict(r.get("demographics", {})),
            )
        )
        r_added += 1
        for flag in r.get("dietary_flags", []):
            session.add(
                ResidentDietaryFlag(
                    resident_id=r["id"],
                    flag=DietaryFlag(flag),
                )
            )
            f_added += 1
    session.commit()
    return r_added, f_added


def _parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 timestamp (trailing Z treated as UTC)."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    # Strip tz so it matches the naive UTC datetimes produced elsewhere in Phase 1.
    return dt.replace(tzinfo=None)


def _seed_demo_orders(session: Session) -> tuple[int, int, int]:
    """Load fixtures/demo_orders.json. Idempotent on Order.id.

    Returns (orders_inserted, order_lines_inserted, status_events_inserted).
    """
    path = FIXTURES_DIR / "demo_orders.json"
    if not path.exists():
        return (0, 0, 0)
    data = _load_json("demo_orders.json")

    o_added = 0
    l_added = 0
    e_added = 0
    for o in data:
        existing = session.exec(select(Order).where(Order.id == o["id"])).first()
        if existing is not None:
            continue
        session.add(
            Order(
                id=o["id"],
                facility_id=o["facility_id"],
                placed_by_user_id=o["placed_by_user_id"],
                meal_plan_id=o.get("meal_plan_id"),
                status=OrderStatus(o["status"]),
                total_cents=o["total_cents"],
                submitted_at=_parse_iso(o["submitted_at"]),
                delivery_date=date.fromisoformat(o["delivery_date"]),
                delivery_window_slot=o["delivery_window_slot"],
                notes=o.get("notes"),
            )
        )
        session.flush()
        o_added += 1

        for ln in o.get("lines", []):
            session.add(
                OrderLine(
                    order_id=o["id"],
                    recipe_id=ln["recipe_id"],
                    n_servings=ln["n_servings"],
                    unit_price_cents=ln["unit_price_cents"],
                    line_total_cents=ln["line_total_cents"],
                    pricing_source=PricingSource(ln.get("pricing_source", "static")),
                )
            )
            l_added += 1

        for ev in o.get("status_events", []):
            session.add(
                OrderStatusEvent(
                    order_id=o["id"],
                    from_status=OrderStatus(ev["from_status"])
                    if ev.get("from_status")
                    else None,
                    to_status=OrderStatus(ev["to_status"]),
                    note=ev.get("note"),
                    occurred_at=_parse_iso(ev["occurred_at"]),
                )
            )
            e_added += 1
    session.commit()
    return o_added, l_added, e_added


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
        res, flags = _seed_residents(session)
        orders, lines, events = _seed_demo_orders(session)

    print(
        f"Seeded: {f} facilities, {u} admin users, {r} recipes, "
        f"{i} recipe-ingredient links, {res} residents, {flags} dietary flags, "
        f"{orders} demo orders ({lines} lines, {events} status events)."
    )


if __name__ == "__main__":
    main()


# Phase 2 Graduation: move to Alembic data migrations.
