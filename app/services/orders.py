"""
PSEUDOCODE:
1. Purpose: Single source of truth for Order mutation. Implements
   the state machine from DOMAIN-WORKFLOW.md Section 3, the
   MealPlan -> Order generator (J3 post-save hook), and the read-side
   helpers for history + detail pages (J5).
2. Ordered algorithm:
   - advance_order_status:
       a. Load Order by id.
       b. key = (order.status, new_status); look up in
          ORDER_TRANSITIONS; raise InvalidTransition if missing.
       c. Evaluate guard predicate(order, note, caller_context);
          raise GuardFailed on False.
       d. Update Order.status = new_status.
       e. Append OrderStatusEvent(from=old, to=new, note, now()).
       f. Commit, return fresh Order.
   - generate_from_meal_plan:
       a. Load MealPlan + MealPlanSlot rows (ordered by
          day_of_week, meal_type).
       b. Group slots by day_of_week.
       c. For each day:
            delivery_date = meal_plan.week_start + timedelta(day)
            order = Order(facility_id=meal_plan.facility_id,
                          placed_by_user_id=meal_plan.created_by_user_id,
                          meal_plan_id=meal_plan.id,
                          status="pending",
                          delivery_date=delivery_date,
                          submitted_at=now(),
                          total_cents=0)
            for slot in day_slots:
                rollup = pricing.static_rollup(slot.recipe_id,
                                               slot.n_servings)
                order.lines.append(OrderLine(
                    recipe_id=slot.recipe_id,
                    n_servings=slot.n_servings,
                    unit_price_cents=rollup["per_serving_cents"],
                    line_total_cents=rollup["total_cents"]))
                order.total_cents += rollup["total_cents"]
            append OrderStatusEvent(null->pending)
       d. Return list[Order].
   - get_order_with_timeline: read-side join of Order + lines + events.
   - list_orders_for_facility: paginated, optional status filter.
3. Inputs / Outputs: see function signatures below.
4. Side effects: Writes Order, OrderLine, OrderStatusEvent. Reads
   MealPlan/MealPlanSlot/Recipe. Calls pricing.static_rollup()
   (pure). No LLM calls. All mutations routed through
   advance_order_status — no other code may set Order.status.

IMPLEMENTATION: Phase 4.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict

# ---------------------------------------------------------------------------
# Order transition table — DOMAIN-WORKFLOW.md Section 3.
# Each key is (from_status, to_status); value is a guard predicate:
#   guard(order, note, caller_context) -> bool
# Guards are *pure* predicates except they may read the current clock.
# ORDER_TRANSITIONS is the ONLY authoritative transition registry.
# ---------------------------------------------------------------------------

GuardFn = Callable[[Any, str, dict], bool]


def _guard_can_confirm(order: Any, note: str, ctx: dict) -> bool:
    # PSEUDO:
    #   return ctx.get("role") == "admin" \
    #          and commissary_capacity_ok(order)   # stub returns True
    raise NotImplementedError("Phase 4")


def _guard_cancel_pending(order: Any, note: str, ctx: dict) -> bool:
    # PSEUDO: order.status == "pending"
    raise NotImplementedError("Phase 4")


def _guard_start_prep(order: Any, note: str, ctx: dict) -> bool:
    # PSEUDO:
    #   return (order.delivery_date - now()).total_seconds() <= 24*3600
    raise NotImplementedError("Phase 4")


def _guard_cancel_confirmed(order: Any, note: str, ctx: dict) -> bool:
    # PSEUDO:
    #   return ctx.get("role") == "admin" \
    #          and (order.delivery_date - now()).total_seconds() >= 6*3600
    raise NotImplementedError("Phase 4")


def _guard_load_truck(order: Any, note: str, ctx: dict) -> bool:
    # PSEUDO:
    #   return now() >= datetime.combine(order.delivery_date, time(5,0))
    raise NotImplementedError("Phase 4")


def _guard_deliver(order: Any, note: str, ctx: dict) -> bool:
    # PSEUDO: ctx.get("role") in {"admin", "driver"}
    raise NotImplementedError("Phase 4")


ORDER_TRANSITIONS: dict[tuple[str, str], GuardFn] = {
    ("pending",         "confirmed"):         _guard_can_confirm,
    ("pending",         "cancelled"):         _guard_cancel_pending,
    ("confirmed",       "in_preparation"):    _guard_start_prep,
    ("confirmed",       "cancelled"):         _guard_cancel_confirmed,
    ("in_preparation",  "out_for_delivery"):  _guard_load_truck,
    ("out_for_delivery", "delivered"):        _guard_deliver,
}
# Any transition key not present here is explicitly rejected.


class InvalidTransition(Exception):
    """Raised when (from_status, to_status) is not in ORDER_TRANSITIONS."""


class GuardFailed(Exception):
    """Raised when a transition's guard predicate evaluates False."""


class PagedOrders(TypedDict):
    items: list[dict]
    page: int
    page_size: int
    total: int
    total_pages: int


def advance_order_status(
    order_id: int,
    new_status: str,
    note: str = "",
    caller_context: dict | None = None,
) -> Any:
    # PSEUDO:
    #   1. ctx   = caller_context or {}
    #   2. order = load Order(order_id)                    # app.models.order
    #   3. key   = (order.status, new_status)
    #      guard = ORDER_TRANSITIONS.get(key)
    #      if guard is None: raise InvalidTransition(key)
    #   4. if not guard(order, note, ctx):
    #          raise GuardFailed(key)
    #   5. old = order.status
    #      order.status = new_status
    #      event = OrderStatusEvent(order_id=order.id,
    #                               from_status=old,
    #                               to_status=new_status,
    #                               note=note,
    #                               occurred_at=now())
    #      db.add(event); db.commit()
    #   6. return order
    raise NotImplementedError("Phase 4")


def generate_from_meal_plan(meal_plan_id: int) -> list[Any]:
    # PSEUDO:
    #   1. plan  = load MealPlan(meal_plan_id) with slots eager
    #   2. by_day = groupby(plan.slots, key=lambda s: s.day_of_week)
    #   3. orders = []
    #      for dow, slots in by_day:
    #          delivery_date = plan.week_start + timedelta(days=dow)
    #          order = Order(facility_id=plan.facility_id,
    #                        placed_by_user_id=plan.created_by_user_id,
    #                        meal_plan_id=plan.id,
    #                        status="pending",
    #                        delivery_date=delivery_date,
    #                        submitted_at=now(),
    #                        total_cents=0,
    #                        delivery_window_slot="midday_11_1")
    #          for slot in slots:
    #              r = pricing.static_rollup(slot.recipe_id,
    #                                        slot.n_servings)
    #              order.lines.append(OrderLine(
    #                  recipe_id=slot.recipe_id,
    #                  n_servings=slot.n_servings,
    #                  unit_price_cents=r["per_serving_cents"],
    #                  line_total_cents=r["total_cents"]))
    #              order.total_cents += r["total_cents"]
    #          db.add(order); db.flush()
    #          db.add(OrderStatusEvent(order_id=order.id,
    #                                  from_status=None,
    #                                  to_status="pending",
    #                                  note="generated from MealPlan",
    #                                  occurred_at=now()))
    #          orders.append(order)
    #      db.commit()
    #   4. return orders
    raise NotImplementedError("Phase 4")


def get_order_with_timeline(order_id: int) -> dict:
    # PSEUDO:
    #   1. order  = load Order(order_id) with lines + events eager
    #   2. lines  = [{"recipe_id": L.recipe_id, "title": L.recipe.title,
    #                 "n_servings": L.n_servings,
    #                 "unit_price_cents": L.unit_price_cents,
    #                 "line_total_cents": L.line_total_cents}
    #                for L in order.lines]
    #   3. events = sorted(order.events, key=lambda e: e.occurred_at)
    #      timeline = [{"from": e.from_status, "to": e.to_status,
    #                   "note": e.note,
    #                   "occurred_at": e.occurred_at.isoformat()}
    #                  for e in events]
    #   4. return {"order": {...scalar order fields...},
    #              "lines": lines,
    #              "timeline": timeline}
    raise NotImplementedError("Phase 4")


def list_orders_for_facility(
    facility_id: int,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> PagedOrders:
    # PSEUDO:
    #   1. q = SELECT Order WHERE facility_id = :facility_id
    #   2. if status_filter: q = q.where(Order.status == status_filter)
    #   3. total = q.count()
    #   4. rows  = q.order_by(Order.delivery_date.desc()) \
    #               .offset((page-1)*page_size).limit(page_size).all()
    #   5. items = [serialize_order_row(r) for r in rows]
    #   6. return {"items": items, "page": page, "page_size": page_size,
    #              "total": total,
    #              "total_pages": ceil(total / page_size) if total else 1}
    raise NotImplementedError("Phase 4")


# Phase 2 Graduation: services/orders.py::advance_order_status() — emit
# an Inngest event after each commit so kitchen, logistics, and
# notification handlers can fan out; table + guards remain unchanged.
