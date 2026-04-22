"""
Calendar view-model — pure-stdlib month grid for /calendar.

No JS libs, no third-party calendar package — `calendar.monthcalendar` is the engine.
Contract: DOMAIN-WORKFLOW.md §7.
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.order import Order, OrderStatus


class OrderSummary(TypedDict):
    id: int
    status: str
    total_cents: int


class DayCell(TypedDict):
    date: date | None
    day_of_month: int
    in_month: bool
    is_today: bool
    orders: list[OrderSummary]


class YearMonth(TypedDict):
    year: int
    month: int


class MonthGrid(TypedDict):
    year: int
    month: int
    weeks: list[list[DayCell]]
    prev: YearMonth
    next: YearMonth
    today: date


def _prev_month(year: int, month: int) -> YearMonth:
    if month == 1:
        return {"year": year - 1, "month": 12}
    return {"year": year, "month": month - 1}


def _next_month(year: int, month: int) -> YearMonth:
    if month == 12:
        return {"year": year + 1, "month": 1}
    return {"year": year, "month": month + 1}


def _status_str(s) -> str:
    return s.value if isinstance(s, OrderStatus) else str(s)


async def build_month_grid(
    session: AsyncSession,
    year: int | None,
    month: int | None,
    facility_id: int,
    *,
    today: date | None = None,
) -> MonthGrid:
    """Build the month-grid view-model for `/calendar`.

    `today` is injected so tests can freeze the is_today highlight without
    mocking the system clock.
    """
    today = today or date.today()
    if not year:
        year = today.year
    if not month:
        month = today.month
    if not (1 <= month <= 12):
        raise ValueError(f"month out of range: {month}")

    weeks_int = calendar.monthcalendar(year, month)
    valid_days = [d for row in weeks_int for d in row if d]
    first_day = date(year, month, 1)
    last_day = date(year, month, max(valid_days))

    rows = (
        await session.execute(
            select(Order)
            .where(Order.facility_id == facility_id)
            .where(Order.delivery_date >= first_day)
            .where(Order.delivery_date <= last_day)
        )
    ).scalars().all()

    orders_by_date: dict[date, list[OrderSummary]] = {}
    for r in rows:
        orders_by_date.setdefault(r.delivery_date, []).append(
            {
                "id": r.id,
                "status": _status_str(r.status),
                "total_cents": r.total_cents,
            }
        )

    weeks: list[list[DayCell]] = []
    for row in weeks_int:
        cells: list[DayCell] = []
        for d in row:
            if d == 0:
                cells.append(
                    DayCell(
                        date=None,
                        day_of_month=0,
                        in_month=False,
                        is_today=False,
                        orders=[],
                    )
                )
            else:
                cell_date = date(year, month, d)
                cells.append(
                    DayCell(
                        date=cell_date,
                        day_of_month=d,
                        in_month=True,
                        is_today=(cell_date == today),
                        orders=orders_by_date.get(cell_date, []),
                    )
                )
        weeks.append(cells)

    return MonthGrid(
        year=year,
        month=month,
        weeks=weeks,
        prev=_prev_month(year, month),
        next=_next_month(year, month),
        today=today,
    )


# Phase 2 Graduation: expose the same shape as /api/v1/calendar JSON; a
# React/FullCalendar client consumes the JSON twin while Jinja keeps working.
