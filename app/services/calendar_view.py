"""
PSEUDOCODE:
1. Purpose: Build a pure-stdlib month-grid view-model for the
   /calendar route (DOMAIN-WORKFLOW.md Section 7). No JS libraries,
   no third-party calendar package — Python `calendar.monthcalendar`
   is the engine.
2. Ordered algorithm:
   a. Validate (year, month); default to today when missing.
   b. Call calendar.monthcalendar(year, month) -> list[list[int]].
      (Week rows; 0 denotes a day outside the month.)
   c. Compute first_day, last_day of the month.
   d. SELECT Order WHERE facility_id = :fid
        AND delivery_date BETWEEN first_day AND last_day.
      Group into dict[date, list[OrderSummary]].
   e. For each week row, for each day int, build a DayCell:
        - date = date(year, month, day) if day else None
        - day_of_month = day
        - in_month = bool(day)
        - is_today = (date == today)
        - orders = orders_by_date.get(date, [])
   f. Compute prev/next (year, month) with wrap at Jan/Dec.
   g. Return {weeks, prev, next, today, year, month}.
3. Inputs / Outputs:
   - Inputs: int year, int month, int facility_id.
   - Output: MonthGrid dict (see below).
4. Side effects: One read-only SELECT of Orders for the month.

IMPLEMENTATION: Phase 4.
"""

from __future__ import annotations

from datetime import date
from typing import TypedDict


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
    # PSEUDO:
    #   if month == 1: return {"year": year - 1, "month": 12}
    #   return {"year": year, "month": month - 1}
    raise NotImplementedError("Phase 4")


def _next_month(year: int, month: int) -> YearMonth:
    # PSEUDO:
    #   if month == 12: return {"year": year + 1, "month": 1}
    #   return {"year": year, "month": month + 1}
    raise NotImplementedError("Phase 4")


def build_month_grid(year: int, month: int, facility_id: int) -> MonthGrid:
    # PSEUDO:
    #   1. today = date.today()
    #      if not year or not month:
    #          year, month = today.year, today.month
    #      if not (1 <= month <= 12): raise ValueError
    #   2. weeks_int = calendar.monthcalendar(year, month)
    #      last_day_num = max(d for row in weeks_int for d in row if d)
    #      first_day = date(year, month, 1)
    #      last_day  = date(year, month, last_day_num)
    #   3. rows = SELECT id, status, total_cents, delivery_date
    #             FROM "order"
    #             WHERE facility_id = facility_id
    #               AND delivery_date BETWEEN first_day AND last_day
    #      orders_by_date: dict[date, list[OrderSummary]] = {}
    #      for r in rows:
    #          orders_by_date.setdefault(r.delivery_date, []).append(
    #              {"id": r.id, "status": r.status,
    #               "total_cents": r.total_cents})
    #   4. weeks = []
    #      for row in weeks_int:
    #          cells = []
    #          for d in row:
    #              if d == 0:
    #                  cell = DayCell(date=None, day_of_month=0,
    #                                 in_month=False, is_today=False,
    #                                 orders=[])
    #              else:
    #                  cell_date = date(year, month, d)
    #                  cell = DayCell(
    #                      date=cell_date, day_of_month=d,
    #                      in_month=True,
    #                      is_today=(cell_date == today),
    #                      orders=orders_by_date.get(cell_date, []))
    #              cells.append(cell)
    #          weeks.append(cells)
    #   5. return MonthGrid(
    #        year=year, month=month, weeks=weeks,
    #        prev=_prev_month(year, month),
    #        next=_next_month(year, month),
    #        today=today,
    #      )
    raise NotImplementedError("Phase 4")


# Phase 2 Graduation: services/calendar_view.py::build_month_grid() —
# expose the same shape as /api/v1/calendar JSON; a React/FullCalendar
# client consumes the JSON twin; the Jinja template keeps working.
