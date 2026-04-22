"""Unit tests for agents.tools_sdk — the NL ordering @tool wrappers."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from agents import tools_sdk


def _body(response: dict) -> dict:
    """Extract the JSON payload from an MCP content envelope."""
    return json.loads(response["content"][0]["text"])


@pytest.mark.asyncio
async def test_resolve_recipe_success(seeded_db):
    response = await tools_sdk.resolve_recipe({"name_query": "Overnight Oats"})
    assert response["isError"] is False
    body = _body(response)
    assert body["count"] >= 1
    assert body["candidates"][0]["title"] == "Overnight Oats"


@pytest.mark.asyncio
async def test_resolve_recipe_no_match_is_error(seeded_db):
    response = await tools_sdk.resolve_recipe({"name_query": "asdfghjk_nope"})
    assert response["isError"] is True
    body = _body(response)
    assert body["error"]["code"] == "no_match"


@pytest.mark.asyncio
async def test_resolve_recipe_invalid_input(seeded_db):
    response = await tools_sdk.resolve_recipe({})
    assert response["isError"] is True
    body = _body(response)
    assert body["error"]["code"] == "invalid_input"


@pytest.mark.asyncio
async def test_scale_recipe_success(seeded_db):
    response = await tools_sdk.scale_recipe({"recipe_id": 3, "n_servings": 50})
    assert response["isError"] is False
    body = _body(response)
    assert body["n_servings"] == 50
    assert body["line_total_cents"] == body["unit_price_cents"] * 50


@pytest.mark.asyncio
async def test_scale_recipe_unknown_recipe(seeded_db):
    response = await tools_sdk.scale_recipe({"recipe_id": 9999, "n_servings": 1})
    assert response["isError"] is True
    body = _body(response)
    assert body["error"]["code"] == "recipe_not_found"


@pytest.mark.asyncio
async def test_scale_recipe_invalid_input(seeded_db):
    response = await tools_sdk.scale_recipe({"recipe_id": "not-an-int"})
    assert response["isError"] is True


@pytest.mark.asyncio
async def test_check_inventory_is_stub_ok(seeded_db):
    response = await tools_sdk.check_inventory({"recipe_id": 3, "n_servings": 50})
    assert response["isError"] is False
    body = _body(response)
    assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_schedule_order_refuses_without_confirmed(seeded_db):
    response = await tools_sdk.schedule_order(
        {"facility_id": 2, "placed_by_user_id": 1, "recipe_id": 3, "n_servings": 50,
         "unit_price_cents": 280, "delivery_date": str(date.today())}
    )
    assert response["isError"] is True
    body = _body(response)
    assert body["error"]["code"] == "not_confirmed"


@pytest.mark.asyncio
async def test_schedule_order_persists_and_is_idempotent(seeded_db):
    delivery = (date.today() + timedelta(days=6)).isoformat()
    args = {
        "facility_id": 2,
        "placed_by_user_id": 1,
        "recipe_id": 3,
        "n_servings": 40,
        "unit_price_cents": 280,
        "delivery_date": delivery,
        "confirmed": True,
    }
    first = await tools_sdk.schedule_order(args)
    assert first["isError"] is False
    first_body = _body(first)
    assert first_body["duplicate"] is False
    order_id = first_body["order_id"]
    assert order_id > 0

    # Same triple again → duplicate-safe.
    second = await tools_sdk.schedule_order(args)
    second_body = _body(second)
    assert second_body["duplicate"] is True
    assert second_body["order_id"] == order_id


@pytest.mark.asyncio
async def test_schedule_order_invalid_payload(seeded_db):
    response = await tools_sdk.schedule_order({"confirmed": True})
    assert response["isError"] is True
    body = _body(response)
    assert body["error"]["code"] == "invalid_input"
