"""
agents/tools.py — pure async DB helpers used by @tool wrappers in tools_sdk.py.

Each helper opens its own short-lived async session (AGENT-WORKFLOW §5).
No session is shared across calls. No LLM calls. No @tool decorators.

Helpers here back the NL Ordering flow (Slice D). Additional helpers for the
menu-planner will land with Slice E.
"""

from __future__ import annotations

from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import or_
from sqlmodel import select

from app.db.database import get_session
from app.models.order import (
    Order,
    OrderLine,
    OrderStatus,
    OrderStatusEvent,
    PricingSource,
)
from app.models.recipe import Recipe


def _serialize_recipe(r: Recipe) -> dict[str, Any]:
    return {
        "id": r.id,
        "title": r.title,
        "texture_level": r.texture_level,
        "allergens": list(r.allergens or []),
        "cost_cents_per_serving": r.cost_cents_per_serving,
        "prep_time_minutes": r.prep_time_minutes,
        "base_yield": r.base_yield,
    }


async def db_get_recipe(recipe_id: int) -> dict[str, Any] | None:
    """Fetch one recipe by primary key, or None if unknown."""
    async for session in get_session():
        row = await session.get(Recipe, recipe_id)
        return _serialize_recipe(row) if row is not None else None


async def db_search_recipes(
    *,
    name_query: str | None = None,
    exclude_allergens: list[str] | None = None,
    max_cost_cents: int | None = None,
    texture_level_max: int | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Filter the recipe catalog. Filters are AND-combined. Empty filters = all rows (capped).

    Allergen exclusion is applied in Python rather than SQL because the column
    is a JSON list and SQLite's JSON operators vary by build. With ~10 recipes
    in Phase 1 that's trivially cheap.
    """
    async for session in get_session():
        q = select(Recipe)
        if name_query:
            q = q.where(Recipe.title.ilike(f"%{name_query}%"))
        if max_cost_cents is not None:
            q = q.where(Recipe.cost_cents_per_serving <= max_cost_cents)
        if texture_level_max is not None:
            q = q.where(Recipe.texture_level <= texture_level_max)
        q = q.order_by(Recipe.title).limit(limit)

        rows = (await session.execute(q)).scalars().all()
        exclude = {a.lower() for a in (exclude_allergens or [])}
        result: list[dict[str, Any]] = []
        for r in rows:
            if exclude and any(a.lower() in exclude for a in (r.allergens or [])):
                continue
            result.append(_serialize_recipe(r))
        return result


async def db_resolve_recipe(
    name_query: str,
    *,
    top_k: int = 3,
    min_confidence: float = 0.5,
) -> list[dict[str, Any]]:
    """Fuzzy-resolve a recipe name to the top-k candidates above a similarity floor.

    Uses `difflib.SequenceMatcher.ratio()` against the full catalog. Cheap at
    Phase 1 scale (10 recipes). Candidates below min_confidence are dropped.

    Returns a list of {id, title, confidence} dicts, sorted by confidence DESC.
    """
    async for session in get_session():
        rows = (await session.execute(select(Recipe))).scalars().all()
        q = name_query.lower().strip()
        if not q:
            return []

        scored: list[dict[str, Any]] = []
        for r in rows:
            title_lower = r.title.lower()
            ratio = SequenceMatcher(a=q, b=title_lower).ratio()
            if q in title_lower:
                # Proper substring wins over fuzzy ratio — "oats" in "Overnight Oats".
                ratio = max(ratio, 0.85)
            if ratio >= min_confidence:
                scored.append(
                    {
                        "id": r.id,
                        "title": r.title,
                        "confidence": round(ratio, 3),
                    }
                )
        scored.sort(key=lambda d: d["confidence"], reverse=True)
        return scored[:top_k]


async def db_insert_order(
    *,
    facility_id: int,
    placed_by_user_id: int,
    recipe_id: int,
    n_servings: int,
    unit_price_cents: int,
    delivery_date: date,
    delivery_window_slot: str = "midday_11_1",
    notes: str | None = None,
    pricing_source: str = "static",
) -> dict[str, Any]:
    """Persist a single-line Order + OrderLine + initial OrderStatusEvent(pending).

    Atomic transaction. Returns the serialized Order. Used by NL Ordering's
    schedule_order @tool after the user confirms the proposal.
    """
    line_total = unit_price_cents * n_servings
    async for session in get_session():
        order = Order(
            facility_id=facility_id,
            placed_by_user_id=placed_by_user_id,
            meal_plan_id=None,
            status=OrderStatus.PENDING,
            total_cents=line_total,
            submitted_at=datetime.utcnow(),
            delivery_date=delivery_date,
            delivery_window_slot=delivery_window_slot,
            notes=notes,
        )
        session.add(order)
        await session.flush()

        session.add(
            OrderLine(
                order_id=order.id,
                recipe_id=recipe_id,
                n_servings=n_servings,
                unit_price_cents=unit_price_cents,
                line_total_cents=line_total,
                pricing_source=PricingSource(pricing_source),
            )
        )
        session.add(
            OrderStatusEvent(
                order_id=order.id,
                from_status=None,
                to_status=OrderStatus.PENDING,
                note="Order submitted via NL ordering agent.",
                occurred_at=datetime.utcnow(),
            )
        )
        await session.commit()
        await session.refresh(order)
        return {
            "id": order.id,
            "facility_id": order.facility_id,
            "status": order.status.value,
            "total_cents": order.total_cents,
            "delivery_date": order.delivery_date.isoformat(),
            "delivery_window_slot": order.delivery_window_slot,
        }


async def db_find_existing_order(
    *,
    facility_id: int,
    recipe_id: int,
    delivery_date: date,
) -> dict[str, Any] | None:
    """Idempotency lookup: return an existing pending/confirmed order for the
    same (facility, recipe, delivery_date) triple. Used to avoid duplicate
    inserts when the user submits the same NL-ordering text twice.
    """
    async for session in get_session():
        q = (
            select(Order)
            .join(OrderLine, OrderLine.order_id == Order.id)
            .where(Order.facility_id == facility_id)
            .where(Order.delivery_date == delivery_date)
            .where(OrderLine.recipe_id == recipe_id)
            .where(
                or_(
                    Order.status == OrderStatus.PENDING,
                    Order.status == OrderStatus.CONFIRMED,
                )
            )
            .limit(1)
        )
        order = (await session.execute(q)).scalars().first()
        if order is None:
            return None
        return {
            "id": order.id,
            "facility_id": order.facility_id,
            "status": order.status.value,
            "delivery_date": order.delivery_date.isoformat(),
        }
