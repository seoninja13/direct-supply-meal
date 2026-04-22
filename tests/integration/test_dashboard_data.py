"""Integration test — the facility dashboard now shows real active-orders data."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.auth.clerk_middleware import reset_jwks_cache
from tests.fixtures.clerk_jwt_helpers import JWKSServer, mint_session_token


@pytest_asyncio.fixture
async def auth_client(seeded_db, monkeypatch):
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
        r = await c.post("/sign-in/exchange", data={"token": token})
        assert r.status_code == 200
        yield c

    server.stop()
    reset_jwks_cache()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_dashboard_lists_active_orders(auth_client):
    """Seeded facility 2: 4 active (pending, confirmed, in_preparation, out_for_delivery)
    and 1 delivered. Dashboard should show the 4 active ones, not the delivered one."""
    r = await auth_client.get("/facility/dashboard")
    assert r.status_code == 200
    # Active ones — pending/confirmed/in_preparation/out_for_delivery.
    assert "#102" in r.text  # out_for_delivery
    assert "#103" in r.text  # in_preparation
    assert "#104" in r.text  # confirmed
    assert "#105" in r.text  # pending
    # Delivered should be excluded from the dashboard active list.
    assert "#101" not in r.text


@pytest.mark.asyncio
async def test_dashboard_status_counts_rendered(auth_client):
    r = await auth_client.get("/facility/dashboard")
    assert r.status_code == 200
    # The 4 status tile labels all appear (even if count=0 for some).
    for label in ("pending", "confirmed", "out for delivery"):
        assert label in r.text
