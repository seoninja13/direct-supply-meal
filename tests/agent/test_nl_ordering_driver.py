"""Driver tests for agents.drivers.nl_ordering.NLOrderingDriver.

All tests inject a fake `query_fn` from a canned transcript — no real SDK call.
Tool invocations run for real against the seeded test DB.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlmodel import select

from agents.drivers.nl_ordering import NLOrderingDriver, NLOrderingRequest
from app.db.init_schema import AgentTrace
from app.models.order import Order
from tests.fixtures.transcript_helpers import load_transcript, replay


@pytest_asyncio.fixture
async def session(seeded_db):
    from app.db.database import get_session

    async for s in get_session():
        yield s
        break


@pytest.mark.asyncio
async def test_oats_happy_path_awaits_confirmation(session):
    delivery = (date.today() + timedelta(days=3)).isoformat()
    events = load_transcript(
        "nl_ordering__oats_happy_path",
        substitutions={"__DELIVERY_DATE__": delivery},
    )
    driver = NLOrderingDriver(query_fn=replay(events))

    response = await driver.run(
        NLOrderingRequest(
            text="50 Overnight Oats for Tuesday breakfast",
            user_id=1,
            facility_id=2,
        )
    )

    assert response.status == "awaiting_confirmation"
    assert response.proposal is not None
    assert response.proposal["title"] == "Overnight Oats"
    assert response.proposal["n_servings"] == 50
    assert response.trace_id  # non-empty

    # Tool calls recorded in order.
    names = [tc["name"] for tc in response.tool_calls]
    assert names == ["resolve_recipe", "scale_recipe", "check_inventory"]
    # resolve_recipe called with the expected query.
    assert response.tool_calls[0]["input"] == {"name_query": "Overnight Oats"}
    # scale_recipe called with recipe_id=3, n_servings=50.
    assert response.tool_calls[1]["input"] == {"recipe_id": 3, "n_servings": 50}


@pytest.mark.asyncio
async def test_confirmed_path_persists_order(session):
    delivery = (date.today() + timedelta(days=3)).isoformat()
    events = load_transcript(
        "nl_ordering__oats_confirmed_persist",
        substitutions={"__DELIVERY_DATE__": delivery, "__ORDER_ID__": "pending"},
    )
    # The assistant_message "pending" event carries __ORDER_ID__ as a
    # sentinel string — the real driver reads it from the event directly.
    # For the persist-path test we care that schedule_order ran and a real
    # order_id is returned by the tool. We'll overwrite the sentinel in
    # the event to None so the test reads the order_id from the tool_calls.
    events[-1]["order_id"] = None

    driver = NLOrderingDriver(query_fn=replay(events))

    response = await driver.run(
        NLOrderingRequest(
            text="50 Overnight Oats for Tuesday breakfast",
            user_id=1,
            facility_id=2,
            confirm=True,
        )
    )

    assert response.status == "pending"
    # schedule_order tool call must have fired and returned a real order_id.
    schedule_call = next(
        tc for tc in response.tool_calls if tc["name"] == "schedule_order"
    )
    result_body = schedule_call["result"]
    assert result_body["isError"] is False
    import json as _json
    tool_payload = _json.loads(result_body["content"][0]["text"])
    assert tool_payload["order_id"] > 0
    assert tool_payload["status"] == "pending"
    assert tool_payload["duplicate"] is False

    # Real Order row exists in DB for that id.
    new_order = await session.get(Order, tool_payload["order_id"])
    assert new_order is not None
    assert new_order.facility_id == 2


@pytest.mark.asyncio
async def test_ambiguous_recipe_returns_disambiguation(session):
    events = load_transcript("nl_ordering__ambiguous_recipe")
    driver = NLOrderingDriver(query_fn=replay(events))

    response = await driver.run(
        NLOrderingRequest(
            text="I want soup",
            user_id=1,
            facility_id=2,
        )
    )
    assert response.status == "disambiguation"
    assert response.options is not None
    assert len(response.options) == 2


@pytest.mark.asyncio
async def test_driver_writes_agent_trace_row(session):
    events = load_transcript("nl_ordering__ambiguous_recipe")
    driver = NLOrderingDriver(query_fn=replay(events))

    before_count = (
        await session.execute(select(AgentTrace))
    ).scalars().all()
    before_n = len(before_count)

    await driver.run(
        NLOrderingRequest(text="soup", user_id=1, facility_id=2)
    )

    after = (await session.execute(select(AgentTrace))).scalars().all()
    assert len(after) == before_n + 1
    latest = after[-1]
    assert latest.agent_name == "nl_ordering"
    assert latest.outcome == "disambiguation"
    assert latest.query_text == "soup"
    assert isinstance(latest.tool_calls_json, list)


@pytest.mark.asyncio
async def test_driver_swallows_unknown_tool_name(session):
    async def bad_transcript(_ctx):
        yield {"type": "tool_use", "name": "nonexistent_tool", "input": {}}
        yield {"type": "assistant_message", "error": {"code": "gave_up", "message": "no progress"}}

    driver = NLOrderingDriver(query_fn=bad_transcript)
    response = await driver.run(
        NLOrderingRequest(text="do something weird", user_id=1, facility_id=2)
    )

    assert response.status == "error"
    # The unknown tool call was recorded with an error shape.
    assert response.tool_calls[0]["result"]["error"] == "unknown_tool"
