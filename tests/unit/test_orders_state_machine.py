"""Unit tests for the Order state machine — pure guard logic, no DB."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services.orders import (
    ORDER_TRANSITIONS,
    _guard_can_confirm,
    _guard_cancel_confirmed,
    _guard_cancel_pending,
    _guard_deliver,
    _guard_load_truck,
    _guard_start_prep,
)


def _order_on(delivery_date: date) -> SimpleNamespace:
    return SimpleNamespace(delivery_date=delivery_date, status="pending")


def test_transition_table_has_exactly_six_legal_pairs():
    assert len(ORDER_TRANSITIONS) == 6
    keys = set(ORDER_TRANSITIONS.keys())
    assert ("pending", "confirmed") in keys
    assert ("pending", "cancelled") in keys
    assert ("confirmed", "in_preparation") in keys
    assert ("confirmed", "cancelled") in keys
    assert ("in_preparation", "out_for_delivery") in keys
    assert ("out_for_delivery", "delivered") in keys


def test_delivered_is_terminal_no_outbound_transitions():
    for (frm, to) in ORDER_TRANSITIONS:
        assert frm != "delivered", f"delivered must not appear as source; got {frm}->{to}"


def test_cancelled_is_terminal_no_outbound_transitions():
    for (frm, to) in ORDER_TRANSITIONS:
        assert frm != "cancelled", f"cancelled must not appear as source; got {frm}->{to}"


def test_illegal_skip_pending_to_in_preparation_not_in_table():
    assert ("pending", "in_preparation") not in ORDER_TRANSITIONS


def test_illegal_reverse_delivered_to_out_for_delivery_not_in_table():
    assert ("delivered", "out_for_delivery") not in ORDER_TRANSITIONS


def test_guard_can_confirm_requires_admin():
    order = _order_on(date.today() + timedelta(days=2))
    assert _guard_can_confirm(order, "", {"role": "admin"}) is True
    assert _guard_can_confirm(order, "", {"role": "kitchen"}) is False
    assert _guard_can_confirm(order, "", {}) is False


def test_guard_cancel_pending_is_unconditional():
    order = _order_on(date.today() + timedelta(days=2))
    assert _guard_cancel_pending(order, "", {}) is True
    assert _guard_cancel_pending(order, "", {"role": "kitchen"}) is True


def test_guard_start_prep_within_24h_passes():
    target = date.today() + timedelta(days=1)
    # "Now" is 12h before target midnight — inside the 24h window.
    now = datetime.combine(target, datetime.min.time()) - timedelta(hours=12)
    order = _order_on(target)
    assert _guard_start_prep(order, "", {"now": now}) is True


def test_guard_start_prep_too_early_fails():
    target = date.today() + timedelta(days=5)
    now = datetime.combine(target, datetime.min.time()) - timedelta(days=3)
    order = _order_on(target)
    assert _guard_start_prep(order, "", {"now": now}) is False


def test_guard_cancel_confirmed_admin_with_6h_buffer():
    target = date.today() + timedelta(days=2)
    now = datetime.combine(target, datetime.min.time()) - timedelta(hours=8)
    order = _order_on(target)
    assert _guard_cancel_confirmed(order, "", {"role": "admin", "now": now}) is True


def test_guard_cancel_confirmed_non_admin_rejected():
    target = date.today() + timedelta(days=2)
    now = datetime.combine(target, datetime.min.time()) - timedelta(hours=8)
    order = _order_on(target)
    assert _guard_cancel_confirmed(order, "", {"role": "kitchen", "now": now}) is False


def test_guard_cancel_confirmed_too_close_fails():
    target = date.today() + timedelta(days=1)
    now = datetime.combine(target, datetime.min.time()) - timedelta(hours=2)
    order = _order_on(target)
    assert _guard_cancel_confirmed(order, "", {"role": "admin", "now": now}) is False


def test_guard_load_truck_at_or_after_5am():
    target = date.today()
    earliest = datetime.combine(target, datetime.min.time()).replace(hour=5)
    order = _order_on(target)
    assert _guard_load_truck(order, "", {"now": earliest}) is True
    assert _guard_load_truck(order, "", {"now": earliest + timedelta(hours=2)}) is True


def test_guard_load_truck_before_5am_fails():
    target = date.today()
    before = datetime.combine(target, datetime.min.time()).replace(hour=4)
    order = _order_on(target)
    assert _guard_load_truck(order, "", {"now": before}) is False


def test_guard_deliver_admin_or_driver():
    order = _order_on(date.today())
    assert _guard_deliver(order, "", {"role": "admin"}) is True
    assert _guard_deliver(order, "", {"role": "driver"}) is True
    assert _guard_deliver(order, "", {"role": "kitchen"}) is False
    assert _guard_deliver(order, "", {}) is False


@pytest.mark.parametrize(
    "illegal_pair",
    [
        ("pending", "in_preparation"),
        ("pending", "out_for_delivery"),
        ("pending", "delivered"),
        ("confirmed", "out_for_delivery"),
        ("confirmed", "delivered"),
        ("in_preparation", "delivered"),
        ("delivered", "cancelled"),
        ("cancelled", "pending"),
        ("in_preparation", "pending"),
    ],
)
def test_illegal_pairs_absent_from_transition_table(illegal_pair):
    assert illegal_pair not in ORDER_TRANSITIONS
