"""Integration tests for /calendar and /api/v1/calendar."""

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
async def test_calendar_unauthenticated_returns_401(seeded_db):
    from app.main import create_app
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as c:
        r = await c.get("/calendar")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_calendar_april_2026_shows_all_delivery_dates(auth_client):
    """Seeded demo orders for facility 2 deliver on Apr 16, 22, 23, 24, 25."""
    r = await auth_client.get("/calendar?year=2026&month=4")
    assert r.status_code == 200
    # Links to the seeded orders should appear in the rendered HTML.
    for oid in (101, 102, 103, 104, 105):
        assert f"/orders/{oid}" in r.text


@pytest.mark.asyncio
async def test_calendar_json_twin_returns_grid_shape(auth_client):
    r = await auth_client.get("/api/v1/calendar?year=2026&month=4")
    assert r.status_code == 200
    body = r.json()
    assert body["year"] == 2026
    assert body["month"] == 4
    assert body["prev"] == {"year": 2026, "month": 3}
    assert body["next"] == {"year": 2026, "month": 5}
    assert len(body["weeks"]) >= 4

    # Collect all order ids from the grid.
    all_ids = {
        o["id"]
        for week in body["weeks"]
        for cell in week
        for o in cell["orders"]
    }
    assert all_ids == {101, 102, 103, 104, 105}


@pytest.mark.asyncio
async def test_calendar_rejects_invalid_month(auth_client):
    r = await auth_client.get("/calendar?year=2026&month=13")
    # FastAPI Query validation kicks in.
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_calendar_january_prev_wraps_to_december(auth_client):
    r = await auth_client.get("/api/v1/calendar?year=2026&month=1")
    assert r.status_code == 200
    body = r.json()
    assert body["prev"] == {"year": 2025, "month": 12}
