"""
PSEUDOCODE:
1. One-line summary of module purpose.
   - Order state machine tables: OrderStatus enum, Order, OrderLine, OrderStatusEvent per Section 2/3.
2. Ordered steps.
   a. Declare OrderStatus enum (6 values) — enforced by services/orders.py::advance_order_status.
   b. Declare PricingSource enum (static | llm_refined) — audited on every OrderLine per Section 6.
   c. Declare Order SQLModel (total_cents, delivery_window_slot, etc.).
   d. Declare OrderLine SQLModel with unit + line totals and pricing_source.
   e. Declare OrderStatusEvent append-only SQLModel; one row per transition.
3. Inputs / Outputs.
   - Inputs: schedule_order / advance_order_status / generate_from_meal_plan service calls.
   - Outputs: rows rendered by /orders list, /orders/{id} detail timeline, /calendar month grid.
4. Side effects.
   - None at model level. All mutation funnels through services/orders.py (Phase 4).

IMPLEMENTATION: Phase 4 — see functions below.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class OrderStatus(str, Enum):
    # PSEUDO: Canonical order lifecycle states — see Section 3 state machine.
    #   pending -> confirmed|cancelled
    #   confirmed -> in_preparation|cancelled
    #   in_preparation -> out_for_delivery
    #   out_for_delivery -> delivered (terminal)
    #   cancelled (terminal)
    PENDING = "pending"
    CONFIRMED = "confirmed"
    IN_PREPARATION = "in_preparation"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PricingSource(str, Enum):
    # PSEUDO: Pricing provenance persisted on every OrderLine per Section 6.
    #   - static: cost rolled up from recipe.cost_cents_per_serving.
    #   - llm_refined: Haiku wrapper refined price, stayed within 30% of baseline.
    STATIC = "static"
    LLM_REFINED = "llm_refined"


class Order(SQLModel, table=True):
    # PSEUDO: Order table — one delivery to a facility on a specific date.
    #   - id: PK.
    #   - facility_id: FK to facility.id (tenancy).
    #   - placed_by_user_id: FK to user.id (the human in J4 or the generator in J3).
    #   - meal_plan_id: nullable FK (J4 orders are ad-hoc; J3 orders link to the source plan).
    #   - status: OrderStatus enum value. Mutated ONLY via advance_order_status().
    #   - total_cents: sum of OrderLine.line_total_cents at submission. Frozen on cancellation.
    #   - submitted_at: datetime the row was first inserted (pending transition).
    #   - delivery_date: target delivery date (used by calendar view + transition guards).
    #   - delivery_window_slot: DeliveryWindow.value string (morning_6_8 | midday_11_1 | evening_4_6).
    #   - notes: free-form string from the submitter (nullable).
    __tablename__ = "order"

    id: int | None = Field(default=None, primary_key=True)
    facility_id: int = Field(foreign_key="facility.id", index=True)
    placed_by_user_id: int = Field(foreign_key="user.id", index=True)
    meal_plan_id: int | None = Field(default=None, foreign_key="meal_plan.id", index=True)
    status: OrderStatus = Field(default=OrderStatus.PENDING, index=True)
    total_cents: int = Field(default=0)
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    delivery_date: date = Field(index=True)
    delivery_window_slot: str
    notes: str | None = Field(default=None)


class OrderLine(SQLModel, table=True):
    # PSEUDO: OrderLine table — one (recipe, n_servings) row inside an Order.
    #   - id: synthetic PK.
    #   - order_id: FK to order.id (indexed).
    #   - recipe_id: FK to recipe.id (indexed).
    #   - n_servings: integer servings for this line.
    #   - unit_price_cents: price per serving at time of submission.
    #   - line_total_cents: unit_price_cents * n_servings (stored, not computed, for auditability).
    #   - pricing_source: PricingSource enum per Section 6.
    __tablename__ = "order_line"

    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id", index=True)
    recipe_id: int = Field(foreign_key="recipe.id", index=True)
    n_servings: int
    unit_price_cents: int
    line_total_cents: int
    pricing_source: PricingSource = Field(default=PricingSource.STATIC)


class OrderStatusEvent(SQLModel, table=True):
    # PSEUDO: OrderStatusEvent — append-only audit log of transitions.
    #   - id: PK.
    #   - order_id: FK to order.id (indexed — timeline UI queries by order_id ORDER BY occurred_at).
    #   - from_status: OrderStatus or null (null on initial insert).
    #   - to_status: OrderStatus (always set).
    #   - note: optional free-form note (required on cancellation per Section 3 guard table).
    #   - occurred_at: UTC timestamp (defaults to now on INSERT).
    __tablename__ = "order_status_event"

    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id", index=True)
    from_status: OrderStatus | None = Field(default=None)
    to_status: OrderStatus
    note: str | None = Field(default=None)
    occurred_at: datetime = Field(default_factory=datetime.utcnow)


# Phase 2 Graduation: emit an Inngest event on advance_order_status() (kitchen, logistics, notify
# fan-out); add commissary_id FK for multi-kitchen routing; promote delivery_window_slot to a real
# FK into a DeliveryWindow table; add soft-delete + archival for orders > 18 months old.
