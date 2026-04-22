"""Slice A E2E test — Playwright walks /recipes → detail → ingredients.

Requires a live server at BASE_URL (defaults to https://ds-meal.dulocore.com).
This test is SKIPPED when the server is unreachable so CI and local runs don't
flake when DNS or the container isn't up yet — Slice G makes it required.
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


pytestmark = pytest.mark.skipif(
    not _server_reachable(),
    reason=f"Live server at {BASE_URL} not reachable — skip E2E until Slice G deploy.",
)


def test_browse_to_ingredients(page: Page):
    page.goto(f"{BASE_URL}/recipes")
    expect(page.get_by_role("heading", name="Recipes")).to_be_visible()

    page.get_by_role("link", name="Overnight Oats").click()
    expect(page.get_by_role("heading", name="Overnight Oats")).to_be_visible()

    page.get_by_role("link", name=lambda t: t.startswith("Ingredients")).click()
    expect(page.get_by_role("heading", name="Ingredients")).to_be_visible()
    expect(page.locator("table.ingredients tbody tr")).to_have_count(5)
