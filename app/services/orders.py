"""
Order domain service — state machine, read-side queries, timeline loader.

`generate_from_meal_plan` is deferred to Slice E (Menu Planner) per G10.

Contract: DOMAIN-WORKFLOW.md §3 (state machine) + §4 J5 (history/detail).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time
from math import ceil
from typing import Any, TypedDict

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.order import Order, OrderLine, OrderStatus, OrderStatusEvent
from app.models.recipe import Recipe

# ---------------------------------------------------------------------------
# Transition table — DOMAIN-WORKFLOW.md §3.
#
# Each entry maps (from_status, to_status) -> guard(order, note, ctx) -> bool.
# Guards are pure except they may read the current wall-clock (`datetime.utcnow`).
# ORDER_TRANSITIONS is the authoritative transition registry; any pair not
# present here is rejected by `advance_order_status`.
# ---------------------------------------------------------------------------

GuardFn = Callable[[Any, str, dict], bool]


def _guard_can_confirm(order: Any, note: str, ctx: dict) -> bool:
    # Admin-only; commissary capacity check is stubbed True for Phase 1.
    return ctx.get("role") == "admin"


def _guard_cancel_pending(order: Any, note: str, ctx: dict) -> bool:
    # A pending order is always cancellable before commissary accepts it.
    return True


def _guard_start_prep(order: Any, note: str, ctx: dict) -> bool:
    # Kitchen starts prep only within 24h of the delivery date.
    now = ctx.get("now") or datetime.utcnow()
    target = datetime.combine(order.delivery_date, time(0, 0))
    return (target - now).total_seconds() <= 24 * 3600


def _guard_cancel_confirmed(order: Any, note: str, ctx: dict) -> bool:
    # Admin can cancel a confirmed order up to 6h before delivery.
    if ctx.get("role") != "admin":
        return False
    now = ctx.get("now") or datetime.utcnow()
    target = datetime.combine(order.delivery_date, time(0, 0))
    return (target - now).total_seconds() >= 6 * 3600


def _guard_load_truck(order: Any, note: str, ctx: dict) -> bool:
    # Truck loads at 5am on the delivery date.
    now = ctx.get("now") or datetime.utcnow()
    earliest = datetime.combine(order.delivery_date, time(5, 0))
    return now >= earliest


def _guard_deliver(order: Any, note: str, ctx: dict) -> bool:
    # Driver or admin closes the loop on delivery.
    return ctx.get("role") in {"admin", "driver"}


ORDER_TRANSITIONS: dict[tuple[str, str], GuardFn] = {
    ("pending",          "confirmed"):         _guard_can_confirm,
    ("pending",          "cancelled"):         _guard_cancel_pending,
    ("confirmed",        "in_preparation"):    _guard_start_prep,
    ("confirmed",        "cancelled"):         _guard_cancel_confirmed,
    ("in_preparation",   "out_for_delivery"):  _guard_load_truck,
    ("out_for_delivery", "delivered"):         _guard_deliver,
}


class InvalidTransition(Exception):
    """Raised when (from_status, to_status) is not in ORDER_TRANSITIONS."""


class GuardFailed(Exception):
    """Raised when a transition's guard predicate evaluates False."""


class OrderNotFound(Exception):
    """Raised when a lookup misses."""


class PagedOrders(TypedDict):
    items: list[dict]
    page: int
    page_size: int
    total: int
    total_pages: int


def _status_str(s: Any) -> str:
    """Accept OrderStatus enum or plain string; return the string value."""
    return s.value if isinstance(s, OrderStatus) else str(s)


def _serialize_order_row(order: Order) -> dict:
    return {
        "id": order.id,
        "facility_id": order.facility_id,
        "status": _status_str(order.status),
        "total_cents": order.total_cents,
        "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
        "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
        "delivery_window_slot": order.delivery_window_slot,
        "notes": order.notes,
        "meal_plan_id": order.meal_plan_id,
    }


async def advance_order_status(
    session: AsyncSession,
    order_id: int,
    new_status: str,
    note: str = "",
    caller_context: dict | None = None,
) -> Order:
    """Mutate Order.status via the transition table.

    Raises InvalidTransition for unknown pairs, GuardFailed when the guard
    predicate denies the change, OrderNotFound when the id is unknown.
    """
    ctx = caller_context or {}

    order = await session.get(Order, order_id)
    if order is None:
        raise OrderNotFound(order_id)

    from_str = _status_str(order.status)
    to_str = _status_str(new_status)
    key = (from_str, to_str)

    guard = ORDER_TRANSITIONS.get(key)
    if guard is None:
        raise InvalidTransition(key)

    if not guard(order, note, ctx):
        raise GuardFailed(key)

    order.status = OrderStatus(to_str)
    session.add(order)
    session.add(
        OrderStatusEvent(
            order_id=order.id,
            from_status=OrderStatus(from_str),
            to_status=OrderStatus(to_str),
            note=note or None,
            occurred_at=ctx.get("now") or datetime.utcnow(),
        )
    )
    await session.commit()
    await session.refresh(order)
    return order


async def list_orders_for_facility(
    session: AsyncSession,
    facility_id: int,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> PagedOrders:
    """Paginated order list for a single facility, optionally filtered by status.

    Excludes other facilities (tenancy). Ordered by delivery_date DESC so the
    most recent deliveries sit on top.
    """
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 25

    q = select(Order).where(Order.facility_id == facility_id)
    if status_filter:
        q = q.where(Order.status == OrderStatus(status_filter))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await session.execute(count_q)).scalar_one()

    rows_q = (
        q.order_by(Order.delivery_date.desc(), Order.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(rows_q)).scalars().all()

    return {
        "items": [_serialize_order_row(r) for r in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": max(1, ceil(total / page_size)) if total else 1,
    }


async def get_order_with_timeline(
    session: AsyncSession,
    order_id: int,
) -> dict:
    """Fetch one order with its lines (with recipe titles) and full status timeline.

    Raises OrderNotFound when the id doesn't exist. No tenancy check here —
    callers must run `require_facility_access` on the returned facility_id.
    """
    order = await session.get(Order, order_id)
    if order is None:
        raise OrderNotFound(order_id)

    lines_rows = (
        await session.execute(
            select(OrderLine, Recipe)
            .join(Recipe, Recipe.id == OrderLine.recipe_id)
            .where(OrderLine.order_id == order_id)
            .order_by(OrderLine.id)
        )
    ).all()
    lines = [
        {
            "recipe_id": ln.recipe_id,
            "title": rec.title,
            "n_servings": ln.n_servings,
            "unit_price_cents": ln.unit_price_cents,
            "line_total_cents": ln.line_total_cents,
            "pricing_source": ln.pricing_source.value
            if hasattr(ln.pricing_source, "value")
            else str(ln.pricing_source),
        }
        for (ln, rec) in lines_rows
    ]

    events = (
        await session.execute(
            select(OrderStatusEvent)
            .where(OrderStatusEvent.order_id == order_id)
            .order_by(OrderStatusEvent.occurred_at, OrderStatusEvent.id)
        )
    ).scalars().all()

    timeline = [
        {
            "from": _status_str(e.from_status) if e.from_status is not None else None,
            "to": _status_str(e.to_status),
            "note": e.note,
            "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
        }
        for e in events
    ]

    return {
        "order": _serialize_order_row(order),
        "lines": lines,
        "timeline": timeline,
    }


async def generate_from_meal_plan(session: AsyncSession, meal_plan_id: int) -> list[Order]:
    """DEFERRED to Slice E (Menu Planner).

    See PSEUDOCODE in prior revision + DOMAIN-WORKFLOW.md §4 J3 post-save hook.
    Explicit NotImplementedError so any Slice D call fails loudly rather than
    silently generating zero orders.
    """
    raise NotImplementedError("generate_from_meal_plan ships with Slice E")


def progress_fraction(status: str) -> float:
    """Fraction (0.0 - 1.0) of the progress bar to fill for a given status.

    cancelled collapses to 0.0 and the template renders the bar greyed-out.
    """
    s = _status_str(status)
    if s == "cancelled":
        return 0.0
    order = {
        "pending": 1,
        "confirmed": 2,
        "in_preparation": 3,
        "out_for_delivery": 4,
        "delivered": 5,
    }
    step = order.get(s, 0)
    return step / 5.0


# Phase 2 Graduation: emit an Inngest event after each advance_order_status()
# commit so kitchen, logistics, and notification handlers can fan out. The
# transition table itself stays unchanged.
