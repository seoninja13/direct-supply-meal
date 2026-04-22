"""
agents/drivers/nl_ordering.py — NL Ordering L1 Director (transcript-driven).

Design (Phase 1):
- The driver is an adapter between an HTTP request and a multi-turn LLM
  transcript. Each transcript event is either:
      {"type": "tool_use", "name": "...", "input": {...}}
          → driver dispatches to TOOL_REGISTRY, appends the result.
      {"type": "assistant_message", "awaiting_confirmation": True,
       "proposal": {...}}
          → driver halts and returns the proposal for the UI to show.
      {"type": "assistant_message", "pending": True, "order_id": N}
          → driver returns the persisted order_id.
      {"type": "assistant_message", "error": {...}} or
       {"type": "disambiguation", "options": [...]}
          → driver returns an error or disambiguation response.

- `query_fn` is a dependency that yields these events. In production it's a
  wrapper around `claude_agent_sdk.query()` that converts the SDK's tool_use
  blocks into the shape above. In tests we inject a fake transcript.

- `trace_id` is a UUID minted at the start of the call. The unconfirmed path
  returns it so the UI can send it back on POST-with-confirm.

- observability.record_outcome is called in `finally` regardless of outcome.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

from agents.observability import record_outcome
from agents.tools_sdk import TOOL_REGISTRY

logger = logging.getLogger(__name__)

# Type alias: a transcript is an async iterator of event dicts.
TranscriptFn = Callable[[dict[str, Any]], AsyncIterator[dict[str, Any]]]


@dataclass
class NLOrderingRequest:
    text: str
    user_id: int
    facility_id: int
    trace_id: str | None = None  # Set when resuming after user confirmation.
    confirm: bool = False


@dataclass
class NLOrderingResponse:
    status: str  # "awaiting_confirmation" | "pending" | "error" | "disambiguation"
    trace_id: str
    proposal: dict[str, Any] | None = None
    order_id: int | None = None
    error: dict[str, Any] | None = None
    options: list[dict[str, Any]] | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


async def _default_query_fn(
    context: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    """Production transcript source — wraps claude_agent_sdk.query().

    Phase 1: raises NotImplementedError so anyone who tries to run the real
    LLM path without installing + mounting the SDK credentials fails loudly.
    Slice D tests always inject a fake transcript, so this branch only runs
    once the container is rebuilt and the SDK creds are mounted.
    """
    raise NotImplementedError(
        "Real Claude Agent SDK transcript is disabled until the container is "
        "rebuilt with /root/.claude/.credentials.json mounted. Tests inject a "
        "fake query_fn."
    )
    yield  # pragma: no cover — makes the signature an async generator.


def _order_id_from_tools(tool_calls: list[dict[str, Any]]) -> int | None:
    """Scan recorded tool_calls for the last successful schedule_order and
    return its order_id. Used when the assistant emits `pending` without
    explicitly echoing the id.
    """
    import json as _json

    for tc in reversed(tool_calls):
        if tc.get("name") != "schedule_order":
            continue
        result = tc.get("result") or {}
        if result.get("isError"):
            continue
        try:
            body = _json.loads(result["content"][0]["text"])
        except (KeyError, IndexError, ValueError):
            continue
        oid = body.get("order_id")
        if isinstance(oid, int) and oid > 0:
            return oid
    return None


class NLOrderingDriver:
    """L1 Director for NL ordering. One instance per HTTP request."""

    agent_name = "nl_ordering"

    def __init__(self, query_fn: TranscriptFn | None = None) -> None:
        self._query_fn = query_fn or _default_query_fn

    async def run(self, request: NLOrderingRequest) -> NLOrderingResponse:
        trace_id = request.trace_id or uuid.uuid4().hex
        started_at = time.monotonic()

        response = NLOrderingResponse(status="error", trace_id=trace_id)
        context = {
            "text": request.text,
            "user_id": request.user_id,
            "facility_id": request.facility_id,
            "confirm": request.confirm,
            "trace_id": trace_id,
        }

        try:
            async for event in self._query_fn(context):
                etype = event.get("type")

                if etype == "tool_use":
                    tool_name = event.get("name", "")
                    tool_args = event.get("input", {}) or {}
                    handler = TOOL_REGISTRY.get(tool_name)
                    if handler is None:
                        response.tool_calls.append(
                            {
                                "name": tool_name,
                                "input": tool_args,
                                "result": {
                                    "content": [],
                                    "isError": True,
                                    "error": "unknown_tool",
                                },
                            }
                        )
                        continue
                    result = await handler(tool_args)
                    response.tool_calls.append(
                        {"name": tool_name, "input": tool_args, "result": result}
                    )

                elif etype == "assistant_message":
                    if event.get("awaiting_confirmation"):
                        response.status = "awaiting_confirmation"
                        response.proposal = event.get("proposal")
                        break
                    if event.get("pending"):
                        response.status = "pending"
                        response.order_id = event.get("order_id") or _order_id_from_tools(
                            response.tool_calls
                        )
                        break
                    if event.get("error"):
                        response.status = "error"
                        response.error = event.get("error")
                        break

                elif etype == "disambiguation":
                    response.status = "disambiguation"
                    response.options = event.get("options") or []
                    break

                # Unknown event type → log and continue.
                else:
                    logger.warning(
                        "NLOrderingDriver: ignoring unknown event type %r", etype
                    )

        except Exception as exc:
            logger.exception("NLOrderingDriver.run raised")
            response.status = "error"
            response.error = {"type": type(exc).__name__, "message": str(exc)}

        finally:
            latency_ms = int((time.monotonic() - started_at) * 1000)
            await record_outcome(
                trace_row={
                    "agent_name": self.agent_name,
                    "query_text": request.text,
                    "tool_calls_json": [
                        {"name": tc["name"], "input": tc["input"]}
                        for tc in response.tool_calls
                    ],
                    "outcome": response.status,
                    "confidence_score": None,
                    "latency_ms": latency_ms,
                    "cost_cents": 0,  # Phase 1 sentinel — cost is recorded by Slice D+.
                    "notes": None,
                },
                payload={
                    "request": context,
                    "tool_calls": response.tool_calls,
                    "response": {
                        "status": response.status,
                        "proposal": response.proposal,
                        "order_id": response.order_id,
                        "error": response.error,
                        "options": response.options,
                    },
                },
            )

        return response


# Phase 2 Graduation:
#   - _default_query_fn wraps `claude_agent_sdk.query(...)` and converts
#     SDK MessageBlock tool_use entries into the transcript event shape above.
#   - ClaudeSDKClient session is created once per request (multi-turn) and
#     disposed via `async with`.
#   - record_outcome grows cost_cents tracking off SDK usage telemetry.
