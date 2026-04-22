"""Unit tests for app.services.calendar_view.build_month_grid."""

from __future__ import annotations

from datetime import date, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderStatus
from app.services.calendar_view import _next_month, _prev_month, build_month_grid


@pytest_asyncio.fixture
async def session(seeded_db) -> AsyncSession:
    from app.db.database import get_session

    async for s in get_session():
        yield s
        break


def test_prev_month_january_wraps_to_december():
    assert _prev_month(2026, 1) == {"year": 2025, "month": 12}


def test_prev_month_normal_case():
    assert _prev_month(2026, 5) == {"year": 2026, "month": 4}


def test_next_month_december_wraps_to_january():
    assert _next_month(2026, 12) == {"year": 2027, "month": 1}


def test_next_month_normal_case():
    assert _next_month(2026, 4) == {"year": 2026, "month": 5}


@pytest.mark.asyncio
async def test_build_month_grid_empty_facility(session):
    grid = await build_month_grid(session, 2026, 4, facility_id=99, today=date(2026, 4, 22))
    assert grid["year"] == 2026
    assert grid["month"] == 4
    # April 2026 spans 5 weeks: Apr 1 (Wed) starts week 1 with Mon/Tue leading blanks.
    assert len(grid["weeks"]) == 5
    for week in grid["weeks"]:
        for cell in week:
            assert cell["orders"] == []


@pytest.mark.asyncio
async def test_build_month_grid_respects_today_highlight(session):
    grid = await build_month_grid(
        session, 2026, 4, facility_id=99, today=date(2026, 4, 22)
    )
    today_cells = [
        cell for week in grid["weeks"] for cell in week if cell["is_today"]
    ]
    assert len(today_cells) == 1
    assert today_cells[0]["date"] == date(2026, 4, 22)


@pytest.mark.asyncio
async def test_build_month_grid_out_of_month_cells_flagged(session):
    grid = await build_month_grid(
        session, 2026, 4, facility_id=99, today=date(2026, 4, 1)
    )
    # First week of April 2026 has leading Mon/Tue blanks (0).
    first_week = grid["weeks"][0]
    blanks = [c for c in first_week if not c["in_month"]]
    assert len(blanks) >= 1
    for c in blanks:
        assert c["date"] is None
        assert c["day_of_month"] == 0
        assert c["orders"] == []


@pytest.mark.asyncio
async def test_build_month_grid_january_prev_wraps(session):
    grid = await build_month_grid(
        session, 2026, 1, facility_id=99, today=date(2026, 1, 15)
    )
    assert grid["prev"] == {"year": 2025, "month": 12}
    assert grid["next"] == {"year": 2026, "month": 2}


@pytest.mark.asyncio
async def test_build_month_grid_december_next_wraps(session):
    grid = await build_month_grid(
        session, 2026, 12, facility_id=99, today=date(2026, 12, 15)
    )
    assert grid["prev"] == {"year": 2026, "month": 11}
    assert grid["next"] == {"year": 2027, "month": 1}


@pytest.mark.asyncio
async def test_build_month_grid_defaults_to_current_when_no_year_or_month(session):
    today = date.today()
    grid = await build_month_grid(session, None, None, facility_id=99)
    assert grid["year"] == today.year
    assert grid["month"] == today.month


@pytest.mark.asyncio
async def test_build_month_grid_rejects_invalid_month(session):
    with pytest.raises(ValueError):
        await build_month_grid(session, 2026, 13, facility_id=99, today=date(2026, 1, 1))


@pytest.mark.asyncio
async def test_build_month_grid_groups_orders_by_date(session):
    # Use facility 88 to avoid colliding with seeded demo orders on facility 2.
    for (oid, day, status) in [
        (3001, 16, "delivered"),
        (3002, 22, "out_for_delivery"),
        (3003, 22, "pending"),  # second order same day
    ]:
        session.add(
            Order(
                id=oid,
                facility_id=88,
                placed_by_user_id=1,
                meal_plan_id=None,
                status=OrderStatus(status),
                total_cents=1000 * oid,
                submitted_at=datetime(2026, 4, 1),
                delivery_date=date(2026, 4, day),
                delivery_window_slot="midday_11_1",
            )
        )
    # Another facility — must NOT appear in grid.
    session.add(
        Order(
            id=3999,
            facility_id=89,
            placed_by_user_id=1,
            meal_plan_id=None,
            status=OrderStatus.PENDING,
            total_cents=99999,
            submitted_at=datetime(2026, 4, 1),
            delivery_date=date(2026, 4, 22),
            delivery_window_slot="midday_11_1",
        )
    )
    await session.commit()

    grid = await build_month_grid(
        session, 2026, 4, facility_id=88, today=date(2026, 4, 22)
    )
    apr_16 = next(
        c for week in grid["weeks"] for c in week if c["date"] == date(2026, 4, 16)
    )
    apr_22 = next(
        c for week in grid["weeks"] for c in week if c["date"] == date(2026, 4, 22)
    )
    assert len(apr_16["orders"]) == 1
    assert apr_16["orders"][0]["id"] == 3001
    assert len(apr_22["orders"]) == 2
    ids_22 = {o["id"] for o in apr_22["orders"]}
    assert ids_22 == {3002, 3003}
    # Cross-facility exclusion.
    assert 3999 not in ids_22
