"""
agents/drivers/nl_ordering.py — NL Ordering L1 Director.

Two paths:

1. **Production** — `_default_query_fn` drives a real `claude_agent_sdk.query()`
   session with the in-process MCP server from `agents.tools_sdk`. Tools run
   inside the SDK's agentic loop. The driver maps SDK `AssistantMessage`
   blocks into the unified transcript event shape below.

2. **Test** — tests inject a fake `query_fn` that yields canned events
   directly. No SDK call. Tool invocations still execute against the real
   seeded test DB so integration coverage is real.

Transcript event shape (shared by both paths):
    {"type": "tool_use", "name": "...", "input": {...}}
    {"type": "tool_result", "name": "...", "result": {...}}
    {"type": "assistant_message", "awaiting_confirmation": True,
     "proposal": {...}}
    {"type": "assistant_message", "pending": True, "order_id": N}
    {"type": "assistant_message", "error": {...}}
    {"type": "disambiguation", "options": [...]}

`trace_id` is minted at the start of each run so the UI can POST it back
on confirm.  observability.record_outcome fires in `finally`.
"""

from __future__ import annotations

import json as _json
import logging
import os
import re
import time
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents.observability import record_outcome
from agents.tools_sdk import TOOL_REGISTRY

logger = logging.getLogger(__name__)

# Tool names from the SDK path are prefixed by the MCP server. TOOL_REGISTRY
# keys are the bare function names (shared with the test/replay path).
_MCP_PREFIX = "mcp__ds_meal_nl_ordering__"

# Type alias: a transcript is an async iterator of event dicts.
TranscriptFn = Callable[[dict[str, Any]], AsyncIterator[dict[str, Any]]]

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "nl_ordering.md"


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


def _load_system_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        logger.exception("Could not load NL ordering system prompt; using fallback")
        return "You are the NL Ordering agent. Parse the user's request, propose an order, and wait for confirmation before persisting."


def _extract_proposal(text: str) -> dict[str, Any] | None:
    """Find the last ```json fenced block in `text` and parse it.

    The NL prompt asks the model to emit a machine-parsable proposal block
    on turn 1. We look for the last ```json ... ``` fence — last wins so the
    model can iterate verbally and then commit at the end.
    """
    if not text:
        return None
    matches = re.findall(r"```json\s*(.+?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if not matches:
        return None
    try:
        parsed = _json.loads(matches[-1].strip())
        if isinstance(parsed, dict):
            return parsed
    except _json.JSONDecodeError:
        return None
    return None


async def _default_query_fn(
    context: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    """Real claude_agent_sdk.query() driver.

    Registers the NL Ordering MCP server (from `agents.tools_sdk`) with the
    SDK, issues one `query()` call with a prompt that includes the user text
    and the request context (user_id, facility_id, confirm flag), and
    streams the SDK's `AssistantMessage` / tool blocks out as unified
    transcript events.

    The SDK handles the agentic tool-use loop itself — this wrapper just
    observes it and converts each interesting block into our event shape.
    """
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        TextBlock,
        ToolResultBlock,
        ToolUseBlock,
        query,
    )

    from agents.tools_sdk import NL_ORDERING_TOOL_NAMES, build_nl_ordering_mcp_server

    # Claude Max OAuth lives at /root/.claude/.credentials.json and is mounted
    # into the container at /home/appuser/.claude/.credentials.json (see
    # docker-compose.yml). The SDK reads those creds automatically when
    # ANTHROPIC_API_KEY is not set. Per DuloCore memory: CLAUDECODE must be
    # unset in-process before invoking the SDK.
    if os.environ.get("CLAUDECODE"):
        os.environ.pop("CLAUDECODE", None)

    mcp_server = build_nl_ordering_mcp_server()
    system_prompt = _load_system_prompt()

    # Build the user-turn prompt. The driver encodes the request context
    # into the prompt so the model knows the facility + user identity and
    # whether it's a first-turn proposal or a post-confirmation persist.
    user_text = context.get("text", "")
    facility_id = context.get("facility_id")
    user_id = context.get("user_id")
    is_confirming = bool(context.get("confirm"))

    if is_confirming:
        # Each query() call is a fresh SDK session with no memory of the prior
        # turn, so we cannot say "use the values you proposed." We include the
        # original request and ask the model to re-resolve then schedule in a
        # single turn.
        prompt = (
            f"The facility staffer said: \"{user_text}\"\n"
            f"facility_id={facility_id}, placed_by_user_id={user_id}.\n\n"
            f"They have just CONFIRMED this order in the UI. Your job this turn "
            f"is to persist it.\n\n"
            f"Steps:\n"
            f"1. Call `mcp__ds_meal_nl_ordering__resolve_recipe` to pick the "
            f"recipe from the user's text.\n"
            f"2. If needed, call `mcp__ds_meal_nl_ordering__scale_recipe` and "
            f"`mcp__ds_meal_nl_ordering__check_inventory` to determine servings.\n"
            f"3. Call `mcp__ds_meal_nl_ordering__schedule_order` with "
            f"confirmed=true, placed_by_user_id={user_id}, "
            f"facility_id={facility_id}, recipe_id, n_servings, "
            f"unit_price_cents, delivery_date (ISO yyyy-mm-dd), and "
            f"delivery_window_slot (e.g. morning_6_8 for breakfast, "
            f"midday_11_1 for lunch, evening_4_6 for dinner).\n"
            f"4. End your response with:\n"
            f"```json\n{{\"status\": \"pending\"}}\n```"
        )
    else:
        prompt = (
            f"facility_id={facility_id}, user_id={user_id}.\n"
            f"User request: {user_text}\n\n"
            f"Use the tools to resolve the recipe, project cost, and check "
            f"inventory, then propose the order. Do NOT call schedule_order "
            f"on this turn. Finish with a ```json``` block containing the "
            f"proposal: {{recipe_id, title, n_servings, unit_price_cents, "
            f"line_total_cents, delivery_date (ISO), delivery_window_slot, "
            f"warnings[] }}."
        )

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        mcp_servers={"ds_meal_nl_ordering": mcp_server},
        allowed_tools=list(NL_ORDERING_TOOL_NAMES),
        permission_mode="bypassPermissions",
        max_turns=8,
        model="claude-haiku-4-5",
    )

    final_text_accum: list[str] = []

    async for message in query(prompt=prompt, options=options):
        # ToolUseBlock + TextBlock live on AssistantMessage; ToolResultBlock
        # lives on UserMessage (the loop-back that feeds tool output to the
        # model). We need both to record tool calls AND their results.
        content = getattr(message, "content", None)
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, ToolUseBlock):
                yield {
                    "type": "tool_use",
                    "id": getattr(block, "id", None),
                    "name": block.name,
                    "input": dict(block.input or {}),
                }
            elif isinstance(block, ToolResultBlock):
                yield {
                    "type": "tool_result",
                    "tool_use_id": block.tool_use_id,
                    "result": {
                        "content": block.content,
                        "isError": bool(block.is_error),
                    },
                }
            elif isinstance(block, TextBlock) and isinstance(message, AssistantMessage):
                final_text_accum.append(block.text)

    # One terminal assistant_message synthesized from the concatenated text.
    full_text = "\n".join(final_text_accum)
    parsed = _extract_proposal(full_text)

    if is_confirming:
        yield {"type": "assistant_message", "pending": True, "order_id": None}
        return

    if parsed is not None:
        yield {
            "type": "assistant_message",
            "awaiting_confirmation": True,
            "proposal": parsed,
        }
    else:
        yield {
            "type": "assistant_message",
            "error": {
                "code": "no_proposal",
                "message": "Agent finished without producing a structured proposal.",
                "raw_text": full_text[:500],
            },
        }


def _order_id_from_tools(tool_calls: list[dict[str, Any]]) -> int | None:
    """Scan recorded tool_calls for the last successful schedule_order and
    return its order_id. Used when the assistant emits `pending` without
    explicitly echoing the id.

    Handles both content shapes:
      - Dict list: [{"type": "text", "text": "<json>"}]  (MCP standard)
      - Block list: [TextBlock(text="<json>")]            (SDK objects)
    """
    import json as _json

    for tc in reversed(tool_calls):
        if tc.get("name") != "schedule_order":
            continue
        result = tc.get("result") or {}
        if not result or result.get("isError"):
            continue
        content = result.get("content") or []
        if not content:
            continue

        first = content[0]
        text = None
        if isinstance(first, dict):
            text = first.get("text")
        else:
            text = getattr(first, "text", None)
        if not isinstance(text, str):
            continue

        try:
            body = _json.loads(text)
        except ValueError:
            continue
        oid = body.get("order_id") if isinstance(body, dict) else None
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
                    tool_use_id = event.get("id")

                    if tool_name.startswith(_MCP_PREFIX):
                        # Production (SDK) path — the SDK's in-process MCP
                        # server has already executed the tool. Record the
                        # call with its id; the result is filled in when the
                        # matching `tool_result` event arrives.
                        response.tool_calls.append(
                            {
                                "id": tool_use_id,
                                "name": tool_name.removeprefix(_MCP_PREFIX),
                                "input": tool_args,
                                "result": None,
                            }
                        )
                        continue

                    # Test/replay path — driver is the executor.
                    handler = TOOL_REGISTRY.get(tool_name)
                    if handler is None:
                        response.tool_calls.append(
                            {
                                "id": tool_use_id,
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
                        {
                            "id": tool_use_id,
                            "name": tool_name,
                            "input": tool_args,
                            "result": result,
                        }
                    )

                elif etype == "tool_result":
                    # Production path: match to the earlier `tool_use` event
                    # by id and fill in the result the SDK produced.
                    tool_use_id = event.get("tool_use_id")
                    result = event.get("result") or {}
                    for tc in reversed(response.tool_calls):
                        if tc.get("id") == tool_use_id and tc.get("result") is None:
                            tc["result"] = result
                            break

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
