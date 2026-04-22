"""Unit tests for agents.observability.record_outcome."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from agents import observability as obs
from app.db.init_schema import AgentTrace


@pytest.fixture
def isolated_log_paths(tmp_path, monkeypatch):
    """Redirect JSONL + payloads writes to tmp_path so tests don't pollute cwd."""
    monkeypatch.setattr(obs, "JSONL_PATH", tmp_path / "agent_trace.jsonl")
    monkeypatch.setattr(obs, "PAYLOADS_DIR", tmp_path / "agent_payloads")
    return tmp_path


@pytest.mark.asyncio
async def test_record_outcome_inserts_row_and_appends_jsonl(
    seeded_db, isolated_log_paths
):
    trace_id = await obs.record_outcome(
        {
            "ts": datetime(2026, 4, 22, 19, 0),
            "agent_name": "nl_ordering",
            "query_text": "50 oats tuesday",
            "tool_calls_json": [{"name": "resolve_recipe"}],
            "outcome": "awaiting_confirmation",
            "latency_ms": 123,
            "cost_cents": 5,
        },
        payload={"request": {"text": "50 oats tuesday"}},
    )
    assert trace_id > 0

    # DB row present.
    from sqlmodel import select

    from app.db.database import get_session

    async for s in get_session():
        rows = (await s.execute(select(AgentTrace))).scalars().all()
        break
    assert any(r.id == trace_id for r in rows)
    row = next(r for r in rows if r.id == trace_id)
    assert row.agent_name == "nl_ordering"
    assert row.outcome == "awaiting_confirmation"
    assert row.latency_ms == 123

    # JSONL line present.
    jsonl = isolated_log_paths / "agent_trace.jsonl"
    assert jsonl.exists()
    lines = [json.loads(line) for line in jsonl.read_text().splitlines() if line.strip()]
    assert any(entry["id"] == trace_id for entry in lines)

    # Payload dumped.
    payload_path = isolated_log_paths / "agent_payloads" / f"{trace_id}.json"
    assert payload_path.exists()
    loaded = json.loads(payload_path.read_text())
    assert loaded["request"]["text"] == "50 oats tuesday"


@pytest.mark.asyncio
async def test_record_outcome_fills_missing_fields_with_defaults(
    seeded_db, isolated_log_paths
):
    trace_id = await obs.record_outcome({"agent_name": "nl_ordering"})
    assert trace_id > 0
    from app.db.database import get_session

    async for s in get_session():
        trace = await s.get(AgentTrace, trace_id)
        break
    assert trace is not None
    assert trace.query_text == ""
    assert trace.outcome == "unknown"
    assert trace.latency_ms == 0
    assert trace.cost_cents == 0
    assert trace.tool_calls_json == []


@pytest.mark.asyncio
async def test_record_outcome_swallows_exceptions_returns_minus_one(
    monkeypatch, isolated_log_paths
):
    async def broken_get_session():
        raise RuntimeError("DB down")
        yield  # pragma: no cover

    monkeypatch.setattr(obs, "get_session", broken_get_session)

    # Must not raise.
    trace_id = await obs.record_outcome({"agent_name": "nl_ordering"})
    assert trace_id == -1
