"""Unit tests for app.services.orders — DB-backed queries + mutation."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.order import Order, OrderLine, OrderStatus, OrderStatusEvent, PricingSource
from app.services import orders as svc


@pytest_asyncio.fixture
async def session(seeded_db) -> AsyncSession:
    """Yield an AsyncSession bound to the seeded test DB."""
    from app.db.database import get_session

    async for s in get_session():
        yield s
        break


async def _insert_order(
    session: AsyncSession,
    *,
    order_id: int,
    facility_id: int,
    status: str,
    delivery_date: date,
    total_cents: int = 0,
    lines: list[dict] | None = None,
    events: list[dict] | None = None,
) -> Order:
    order = Order(
        id=order_id,
        facility_id=facility_id,
        placed_by_user_id=1,
        meal_plan_id=None,
        status=OrderStatus(status),
        total_cents=total_cents,
        submitted_at=datetime.utcnow(),
        delivery_date=delivery_date,
        delivery_window_slot="midday_11_1",
        notes=None,
    )
    session.add(order)
    await session.flush()

    for ln in lines or []:
        session.add(
            OrderLine(
                order_id=order_id,
                recipe_id=ln["recipe_id"],
                n_servings=ln["n_servings"],
                unit_price_cents=ln["unit_price_cents"],
                line_total_cents=ln["line_total_cents"],
                pricing_source=PricingSource(ln.get("pricing_source", "static")),
            )
        )

    for ev in events or []:
        session.add(
            OrderStatusEvent(
                order_id=order_id,
                from_status=OrderStatus(ev["from"]) if ev.get("from") else None,
                to_status=OrderStatus(ev["to"]),
                note=ev.get("note"),
                occurred_at=ev.get("occurred_at", datetime.utcnow()),
            )
        )

    await session.commit()
    return order


@pytest.mark.asyncio
async def test_advance_status_legal_pending_to_confirmed_records_event(session):
    await _insert_order(
        session,
        order_id=900,
        facility_id=2,
        status="pending",
        delivery_date=date.today() + timedelta(days=3),
    )

    updated = await svc.advance_order_status(
        session,
        order_id=900,
        new_status="confirmed",
        note="admin accepted",
        caller_context={"role": "admin"},
    )
    assert updated.status == OrderStatus.CONFIRMED

    events = (
        await session.execute(
            select(OrderStatusEvent).where(OrderStatusEvent.order_id == 900)
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].to_status == OrderStatus.CONFIRMED
    assert events[0].from_status == OrderStatus.PENDING
    assert events[0].note == "admin accepted"


@pytest.mark.asyncio
async def test_advance_status_illegal_pending_to_delivered_raises(session):
    await _insert_order(
        session,
        order_id=901,
        facility_id=2,
        status="pending",
        delivery_date=date.today() + timedelta(days=3),
    )
    with pytest.raises(svc.InvalidTransition):
        await svc.advance_order_status(
            session,
            order_id=901,
            new_status="delivered",
            caller_context={"role": "admin"},
        )


@pytest.mark.asyncio
async def test_advance_status_guard_failed_when_non_admin_confirms(session):
    await _insert_order(
        session,
        order_id=902,
        facility_id=2,
        status="pending",
        delivery_date=date.today() + timedelta(days=3),
    )
    with pytest.raises(svc.GuardFailed):
        await svc.advance_order_status(
            session,
            order_id=902,
            new_status="confirmed",
            caller_context={"role": "kitchen"},
        )


@pytest.mark.asyncio
async def test_advance_status_order_not_found(session):
    with pytest.raises(svc.OrderNotFound):
        await svc.advance_order_status(
            session,
            order_id=9999,
            new_status="confirmed",
            caller_context={"role": "admin"},
        )


@pytest.mark.asyncio
async def test_list_orders_empty_facility_returns_empty_page(session):
    result = await svc.list_orders_for_facility(session, facility_id=99)
    assert result["items"] == []
    assert result["total"] == 0
    assert result["total_pages"] == 1


@pytest.mark.asyncio
async def test_list_orders_pagination_page_1_and_page_2(session):
    # Use facility_id=99 so we don't collide with seeded demo orders on facility 2.
    today = date.today()
    for idx in range(30):
        await _insert_order(
            session,
            order_id=2000 + idx,
            facility_id=99,
            status="pending",
            delivery_date=today + timedelta(days=idx),
        )
    p1 = await svc.list_orders_for_facility(session, facility_id=99, page=1, page_size=25)
    assert p1["page"] == 1
    assert len(p1["items"]) == 25
    assert p1["total"] == 30
    assert p1["total_pages"] == 2

    p2 = await svc.list_orders_for_facility(session, facility_id=99, page=2, page_size=25)
    assert p2["page"] == 2
    assert len(p2["items"]) == 5


@pytest.mark.asyncio
async def test_list_orders_status_filter_only_returns_matching(session):
    today = date.today()
    await _insert_order(
        session, order_id=2100, facility_id=98, status="pending",
        delivery_date=today,
    )
    await _insert_order(
        session, order_id=2101, facility_id=98, status="delivered",
        delivery_date=today + timedelta(days=1),
    )
    await _insert_order(
        session, order_id=2102, facility_id=98, status="delivered",
        delivery_date=today + timedelta(days=2),
    )
    result = await svc.list_orders_for_facility(
        session, facility_id=98, status_filter="delivered"
    )
    assert result["total"] == 2
    assert all(r["status"] == "delivered" for r in result["items"])


@pytest.mark.asyncio
async def test_list_orders_excludes_other_facilities(session):
    today = date.today()
    await _insert_order(
        session, order_id=2200, facility_id=97, status="pending",
        delivery_date=today,
    )
    await _insert_order(
        session, order_id=2201, facility_id=96, status="pending",
        delivery_date=today,
    )
    # Facility 97 sees only its own inserted order (no other seed rows on fac 97).
    r2 = await svc.list_orders_for_facility(session, facility_id=97)
    assert r2["total"] == 1
    assert r2["items"][0]["id"] == 2200


@pytest.mark.asyncio
async def test_get_order_with_timeline_returns_lines_and_events(session):
    await _insert_order(
        session,
        order_id=2300,
        facility_id=2,
        status="delivered",
        delivery_date=date.today(),
        total_cents=25200,
        lines=[
            {"recipe_id": 1, "n_servings": 60, "unit_price_cents": 420,
             "line_total_cents": 25200, "pricing_source": "static"},
        ],
        events=[
            {"from": None,         "to": "pending",   "occurred_at": datetime(2026, 4, 15, 9, 0)},
            {"from": "pending",    "to": "confirmed", "occurred_at": datetime(2026, 4, 15, 10, 0)},
            {"from": "confirmed",  "to": "in_preparation", "occurred_at": datetime(2026, 4, 16, 5, 0)},
            {"from": "in_preparation", "to": "out_for_delivery",
             "occurred_at": datetime(2026, 4, 16, 10, 0)},
            {"from": "out_for_delivery", "to": "delivered",
             "occurred_at": datetime(2026, 4, 16, 12, 0)},
        ],
    )
    result = await svc.get_order_with_timeline(session, order_id=2300)
    assert result["order"]["id"] == 2300
    assert result["order"]["status"] == "delivered"
    assert len(result["lines"]) == 1
    assert result["lines"][0]["title"]  # recipe join resolved
    assert len(result["timeline"]) == 5
    # Timeline is chronologically ordered.
    assert result["timeline"][0]["to"] == "pending"
    assert result["timeline"][-1]["to"] == "delivered"


@pytest.mark.asyncio
async def test_get_order_with_timeline_not_found(session):
    with pytest.raises(svc.OrderNotFound):
        await svc.get_order_with_timeline(session, order_id=99999)


def test_progress_fraction_values():
    assert svc.progress_fraction("pending") == pytest.approx(0.2)
    assert svc.progress_fraction("confirmed") == pytest.approx(0.4)
    assert svc.progress_fraction("in_preparation") == pytest.approx(0.6)
    assert svc.progress_fraction("out_for_delivery") == pytest.approx(0.8)
    assert svc.progress_fraction("delivered") == pytest.approx(1.0)
    assert svc.progress_fraction("cancelled") == 0.0
