"""Integration tests for /orders + /orders/{id} + /api/v1/orders against the FastAPI app.

Uses the same Clerk JWT minting helpers as test_auth.py. The seeded test DB
includes 5 demo orders for Riverside SNF (facility_id=2), admin user id=1.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.auth.clerk_middleware import reset_jwks_cache
from tests.fixtures.clerk_jwt_helpers import JWKSServer, mint_session_token


@pytest_asyncio.fixture
async def auth_client(seeded_db, monkeypatch):
    """AuthN'd client for admin@dulocore.com — already signed in against the dashboard."""
    server = JWKSServer()
    server.start()
    monkeypatch.setenv("CLERK_JWKS_URL", server.url)

    from app.config import get_settings
    get_settings.cache_clear()
    reset_jwks_cache()

    from app.main import create_app
    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = mint_session_token(sub="user_clerk_admin", email="admin@dulocore.com")
        # Exchange the Clerk token for the app session cookie.
        r = await c.post("/sign-in/exchange", data={"token": token})
        assert r.status_code == 200, r.text
        yield c

    server.stop()
    reset_jwks_cache()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_orders_list_unauthenticated_returns_401(seeded_db):
    from app.main import create_app
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as c:
        r = await c.get("/orders")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_orders_list_shows_five_demo_orders(auth_client):
    r = await auth_client.get("/orders")
    assert r.status_code == 200
    # All 5 seeded demo orders appear in the rendered HTML.
    for oid in (101, 102, 103, 104, 105):
        assert f"#{oid}" in r.text


@pytest.mark.asyncio
async def test_orders_list_status_filter_delivered_returns_one(auth_client):
    r = await auth_client.get("/orders?status=delivered")
    assert r.status_code == 200
    # Only order 101 is delivered.
    assert "#101" in r.text
    assert "#102" not in r.text
    assert "#103" not in r.text


@pytest.mark.asyncio
async def test_orders_list_status_filter_invalid_rejected(auth_client):
    r = await auth_client.get("/orders?status=bogus")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_orders_list_json_twin(auth_client):
    r = await auth_client.get("/api/v1/orders")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    assert {item["id"] for item in body["items"]} == {101, 102, 103, 104, 105}


@pytest.mark.asyncio
async def test_order_detail_returns_timeline_and_lines(auth_client):
    r = await auth_client.get("/orders/101")
    assert r.status_code == 200
    # Timeline: 5 status events for order 101.
    # All five status transitions should be represented in the rendered HTML.
    assert "pending" in r.text
    assert "confirmed" in r.text
    assert "in preparation" in r.text
    assert "out for delivery" in r.text
    assert "delivered" in r.text


@pytest.mark.asyncio
async def test_order_detail_json_includes_timeline_of_5(auth_client):
    r = await auth_client.get("/api/v1/orders/101")
    assert r.status_code == 200
    body = r.json()
    assert body["order"]["id"] == 101
    assert body["order"]["status"] == "delivered"
    assert len(body["timeline"]) == 5
    assert len(body["lines"]) == 1


@pytest.mark.asyncio
async def test_order_detail_missing_returns_404(auth_client):
    r = await auth_client.get("/orders/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_order_detail_cross_facility_returns_403(auth_client, seeded_db):
    """Insert an order for another facility (id=3) directly, verify admin@fac2 gets 403."""
    from datetime import date, datetime

    from app.db.database import get_session
    from app.models.order import Order, OrderStatus

    async for s in get_session():
        s.add(
            Order(
                id=7777,
                facility_id=3,  # Cedar Pines — NOT the admin's facility
                placed_by_user_id=1,
                meal_plan_id=None,
                status=OrderStatus.PENDING,
                total_cents=1000,
                submitted_at=datetime.utcnow(),
                delivery_date=date.today(),
                delivery_window_slot="midday_11_1",
            )
        )
        await s.commit()
        break

    r = await auth_client.get("/orders/7777")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_orders_new_renders_form_after_slice_d(auth_client):
    """Slice D replaced the 501 deferral with a live form. Slice D's own
    integration tests (test_orders_new_api.py) exercise POST + transcript
    injection; here we just confirm the GET landing page is live."""
    r = await auth_client.get("/orders/new")
    assert r.status_code == 200
    assert "Place an order" in r.text
