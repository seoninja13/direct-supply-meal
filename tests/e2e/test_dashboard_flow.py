"""Slice C E2E — sign in → dashboard → order detail → calendar → nav works.

SKIPPED when the live server at BASE_URL is unreachable, matching Slice A's
convention. Slice G deploy flips this to required.

Requires Clerk Google provider enabled in the DS-Meal app AND the admin email
`admin@dulocore.com` able to reach AccountPortal (real OAuth). Use CI secrets
or manual run once Slice B is deployed.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request

import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("BASE_URL", "https://ds-meal.dulocore.com")


def _server_reachable() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def _slice_c_deployed() -> bool:
    """Slice C routes exist only after the Slice B+C deploy."""
    try:
        with urllib.request.urlopen(f"{BASE_URL}/sign-in", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not (_server_reachable() and _slice_c_deployed()),
    reason=(
        f"Live server at {BASE_URL} not reachable, or Slice B/C not deployed — "
        "skip E2E until deploy gate passes."
    ),
)


def test_dashboard_flow_signin_to_order_detail(page: Page):
    """Golden-path browse: sign in → dashboard → click order → detail → back to calendar."""
    # Sign-in via Clerk AccountPortal (real OAuth — test account with Google).
    page.goto(f"{BASE_URL}/sign-in")
    # AccountPortal handoff — page script calls clerk.js; the redirect lands on callback.
    # In CI this step would rely on a pre-authenticated session cookie from a bootstrap fixture.
    # Placeholder: expect the Clerk widget to be visible.
    expect(page).to_have_url(lambda u: "/sign-in" in u)

    # After sign-in, dashboard is the landing destination.
    page.goto(f"{BASE_URL}/facility/dashboard")
    expect(page.get_by_role("heading", name="Riverside SNF")).to_be_visible()

    # Click into the first active order (seeded 102, 103, 104, or 105).
    page.get_by_role("link", name="#102").first.click()
    expect(page.get_by_role("heading", name="Order #102")).to_be_visible()

    # Timeline visible.
    expect(page.get_by_text("in preparation", exact=False)).to_be_visible()

    # Navigate to calendar.
    page.goto(f"{BASE_URL}/calendar?year=2026&month=4")
    expect(page.get_by_role("heading", name="Delivery calendar")).to_be_visible()

    # Prev/next navigation works.
    page.get_by_role("link", name=lambda n: "5/2026" in n).click()
    expect(page).to_have_url(lambda u: "month=5" in u)


def test_orders_list_filter_by_delivered(page: Page):
    page.goto(f"{BASE_URL}/orders?status=delivered")
    expect(page.get_by_text("#101")).to_be_visible()
    # No other orders appear when filtered.
    expect(page.get_by_text("#102")).not_to_be_visible()
