"""Integration tests for Clerk sign-in flow + require_login."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.auth.clerk_middleware import reset_jwks_cache
from tests.fixtures.clerk_jwt_helpers import JWKSServer, mint_session_token


@pytest_asyncio.fixture
async def auth_client(seeded_db, monkeypatch):
    """httpx client with Clerk JWKS stubbed via a local HTTP server."""
    server = JWKSServer()
    server.start()
    monkeypatch.setenv("CLERK_JWKS_URL", server.url)

    from app.config import get_settings
    get_settings.cache_clear()
    reset_jwks_cache()

    from app.main import create_app
    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    server.stop()
    reset_jwks_cache()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_dashboard_unauthenticated_returns_401(auth_client):
    resp = await auth_client.get("/facility/dashboard")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_invalid_token_returns_401(auth_client):
    resp = await auth_client.get(
        "/facility/dashboard", headers={"Authorization": "Bearer not.a.token"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_exchange_allowlisted_email_provisions_user(auth_client):
    token = mint_session_token(sub="user_clerk_1", email="admin@dulocore.com")
    resp = await auth_client.post("/sign-in/exchange", data={"token": token})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "signed_in"
    assert body["redirect"] == "/facility/dashboard"


@pytest.mark.asyncio
async def test_exchange_non_allowlisted_email_403(auth_client):
    token = mint_session_token(sub="user_clerk_2", email="stranger@example.com")
    resp = await auth_client.post("/sign-in/exchange", data={"token": token})
    assert resp.status_code == 403
    assert "not_on_allowlist" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_full_sign_in_then_dashboard(auth_client):
    token = mint_session_token(sub="user_clerk_3", email="admin@dulocore.com")

    exchange = await auth_client.post("/sign-in/exchange", data={"token": token})
    assert exchange.status_code == 200

    dash = await auth_client.get("/facility/dashboard")
    assert dash.status_code == 200
    assert "Riverside SNF" in dash.text
    assert "admin@dulocore.com" in dash.text


@pytest.mark.asyncio
async def test_sign_out_redirects_and_clears_cookie(auth_client):
    token = mint_session_token(sub="user_clerk_4", email="admin@dulocore.com")
    await auth_client.post("/sign-in/exchange", data={"token": token})

    resp = await auth_client.post("/sign-out", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


@pytest.mark.asyncio
async def test_api_v1_facility_me_returns_user_and_facility(auth_client):
    token = mint_session_token(sub="user_clerk_5", email="admin@dulocore.com")
    await auth_client.post("/sign-in/exchange", data={"token": token})

    resp = await auth_client.get("/api/v1/facility/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == "admin@dulocore.com"
    assert body["facility"]["name"] == "Riverside SNF"
    assert body["facility"]["type"] == "SNF"
    assert body["facility"]["bed_count"] == 120


@pytest.mark.asyncio
async def test_exchange_expired_token_401(auth_client):
    import time
    token = mint_session_token(
        sub="user_clerk_6",
        email="admin@dulocore.com",
        iat=int(time.time()) - 3600,
        exp=int(time.time()) - 60,
    )
    resp = await auth_client.post("/sign-in/exchange", data={"token": token})
    assert resp.status_code == 401
