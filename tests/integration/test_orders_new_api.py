"""Integration tests for POST /orders/new and POST /api/v1/orders.

Injects a canned transcript by monkeypatching agents.drivers.dispatch.invoke_director.
No real SDK call — transcripts come from tests/fixtures/claude_responses.json.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.auth.clerk_middleware import reset_jwks_cache
from tests.fixtures.clerk_jwt_helpers import JWKSServer, mint_session_token
from tests.fixtures.transcript_helpers import load_transcript, replay


@pytest_asyncio.fixture
async def app_and_dispatch(seeded_db, monkeypatch):
    """Start a JWKS server, mint + exchange a session, yield (client, dispatch_mod)."""
    server = JWKSServer()
    server.start()
    monkeypatch.setenv("CLERK_JWKS_URL", server.url)

    from app.config import get_settings
    get_settings.cache_clear()
    reset_jwks_cache()

    from agents.drivers import dispatch as dispatch_mod
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = mint_session_token(sub="user_clerk_admin", email="admin@dulocore.com")
        r = await c.post("/sign-in/exchange", data={"token": token})
        assert r.status_code == 200
        yield c, dispatch_mod, monkeypatch

    server.stop()
    reset_jwks_cache()
    get_settings.cache_clear()


def _install_fake_dispatcher(dispatch_mod, monkeypatch, events_by_confirm: dict):
    """Swap invoke_director with a fake that picks the transcript by `confirm`.

    `events_by_confirm` keys are True/False → transcript event lists.
    The fake runs the real NLOrderingDriver with an injected query_fn replay.
    """
    from agents.drivers.nl_ordering import NLOrderingDriver, NLOrderingRequest

    async def fake_invoke(director_name, payload):
        assert director_name == "nl_ordering", director_name
        events = events_by_confirm[bool(payload.get("confirm"))]
        driver = NLOrderingDriver(query_fn=replay(events))
        request = NLOrderingRequest(
            text=payload.get("text", ""),
            user_id=int(payload["user_id"]),
            facility_id=int(payload["facility_id"]),
            trace_id=payload.get("trace_id"),
            confirm=bool(payload.get("confirm", False)),
        )
        response = await driver.run(request)
        return {
            "status": response.status,
            "trace_id": response.trace_id,
            "proposal": response.proposal,
            "order_id": response.order_id,
            "error": response.error,
            "options": response.options,
            "tool_calls": response.tool_calls,
        }

    monkeypatch.setattr(dispatch_mod, "invoke_director", fake_invoke)


@pytest.mark.asyncio
async def test_orders_new_get_renders_form(app_and_dispatch):
    client, _, _ = app_and_dispatch
    r = await client.get("/orders/new")
    assert r.status_code == 200
    assert "Place an order" in r.text
    assert "<textarea" in r.text


@pytest.mark.asyncio
async def test_orders_new_post_awaiting_confirmation_renders_proposal(app_and_dispatch):
    client, dispatch_mod, monkeypatch = app_and_dispatch
    delivery = (date.today() + timedelta(days=3)).isoformat()

    events = load_transcript(
        "nl_ordering__oats_happy_path",
        substitutions={"__DELIVERY_DATE__": delivery},
    )
    _install_fake_dispatcher(
        dispatch_mod, monkeypatch, {False: events, True: events}
    )

    r = await client.post(
        "/orders/new",
        data={"text": "50 Overnight Oats for Tuesday breakfast"},
    )
    assert r.status_code == 200
    assert "Confirm this order" in r.text
    assert "Overnight Oats" in r.text
    assert "Confirm &amp; place order" in r.text


@pytest.mark.asyncio
async def test_orders_new_post_with_confirm_redirects_to_detail(app_and_dispatch):
    client, dispatch_mod, monkeypatch = app_and_dispatch
    delivery = (date.today() + timedelta(days=3)).isoformat()

    confirm_events = load_transcript(
        "nl_ordering__oats_confirmed_persist",
        substitutions={"__DELIVERY_DATE__": delivery, "__ORDER_ID__": "42"},
    )
    # The assistant_message emits `order_id` — but the real driver reads
    # it from the `schedule_order` tool result. Set the event's order_id
    # to None so the driver does that. (The tool returns the real id.)
    confirm_events[-1]["order_id"] = None

    _install_fake_dispatcher(
        dispatch_mod, monkeypatch, {True: confirm_events, False: confirm_events}
    )

    r = await client.post(
        "/orders/new",
        data={
            "text": "50 Overnight Oats for Tuesday breakfast",
            "trace_id": "deadbeef",
            "confirm": "yes",
        },
    )
    # The route's RedirectResponse uses 303 — and the test client by default
    # doesn't follow redirects, so we inspect the response directly.
    assert r.status_code == 303
    assert r.headers["location"].startswith("/orders/")


@pytest.mark.asyncio
async def test_orders_new_disambiguation_renders_options(app_and_dispatch):
    client, dispatch_mod, monkeypatch = app_and_dispatch
    events = load_transcript("nl_ordering__ambiguous_recipe")
    _install_fake_dispatcher(
        dispatch_mod, monkeypatch, {False: events, True: events}
    )

    r = await client.post("/orders/new", data={"text": "soup please"})
    assert r.status_code == 200
    assert "Which one did you mean" in r.text
    assert "Tomato Soup" in r.text
    assert "Lentil Soup" in r.text


@pytest.mark.asyncio
async def test_api_v1_orders_post_returns_dispatch_result(app_and_dispatch):
    client, dispatch_mod, monkeypatch = app_and_dispatch
    delivery = (date.today() + timedelta(days=3)).isoformat()
    events = load_transcript(
        "nl_ordering__oats_happy_path",
        substitutions={"__DELIVERY_DATE__": delivery},
    )
    _install_fake_dispatcher(
        dispatch_mod, monkeypatch, {False: events, True: events}
    )

    r = await client.post(
        "/api/v1/orders",
        json={"text": "50 Overnight Oats for Tuesday breakfast"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "awaiting_confirmation"
    assert body["proposal"]["title"] == "Overnight Oats"
    # tool_calls stripped from the JSON response.
    assert "tool_calls" not in body


@pytest.mark.asyncio
async def test_orders_new_unauthenticated_returns_401(seeded_db):
    from app.main import create_app

    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as c:
        r = await c.get("/orders/new")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_orders_new_agent_trace_row_recorded(app_and_dispatch):
    """After POST, agent_trace has one more row (G11 observability)."""
    client, dispatch_mod, monkeypatch = app_and_dispatch
    events = load_transcript("nl_ordering__ambiguous_recipe")
    _install_fake_dispatcher(
        dispatch_mod, monkeypatch, {False: events, True: events}
    )

    from sqlmodel import select

    from app.db.database import get_session
    from app.db.init_schema import AgentTrace

    async for s in get_session():
        before = len((await s.execute(select(AgentTrace))).scalars().all())
        break

    r = await client.post("/orders/new", data={"text": "soup"})
    assert r.status_code == 200

    async for s in get_session():
        after = (await s.execute(select(AgentTrace))).scalars().all()
        break
    assert len(after) == before + 1
    assert after[-1].agent_name == "nl_ordering"
