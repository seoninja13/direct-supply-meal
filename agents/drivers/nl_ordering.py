"""
PSEUDOCODE:
1. NL Ordering L1 Director — Haiku, stateful ClaudeSDKClient, multi-turn with explicit confirmation gate.
2. Turn 1: parse free-text order → propose structured order. Turn 2 (after user confirms): persist.
3. Typical 4-round tool flow: resolve_recipe → scale_recipe → check_inventory → (after confirm) schedule_order.
4. Session-start wiki injection gives the agent learned aliases (e.g., "oats" → Overnight Oats for Riverside SNF).
5. Inputs: NLOrderingRequest { text, user_id, facility_id, trace_id? (for resume), confirm: bool }.
6. Outputs: NLOrderingResponse — either {status:"awaiting_confirmation", proposal:{...}, trace_id} OR {status:"pending", order_id}.
7. Side effects: on confirmed call, writes Order + OrderLine + OrderStatusEvent rows; writes agent_trace row in finally.

IMPLEMENTATION: Phase 4.

Contract: docs/workflows/AGENT-WORKFLOW.md §4.
"""

from dataclasses import dataclass
from typing import Any

# from claude_agent_sdk import ClaudeSDKClient
# from agents.observability import record_outcome
# from agents.tools_sdk import (
#     resolve_recipe, scale_recipe, check_inventory, schedule_order,
# )


@dataclass
class NLOrderingRequest:
    text: str
    user_id: int
    facility_id: int
    trace_id: str | None = None  # set when resuming after confirmation
    confirm: bool = False


@dataclass
class NLOrderingResponse:
    status: str  # "awaiting_confirmation" | "pending" | "error"
    proposal: dict[str, Any] | None
    order_id: int | None
    trace_id: str
    message: str | None


class NLOrderingDirector:
    # PSEUDO:
    # - __init__: load agents/prompts/nl_ordering.md; ClaudeSDKClient(
    #     model="claude-haiku-4-5", retry=3, escalation=True, max_turns=6,
    #     tools=[resolve_recipe, scale_recipe, check_inventory, schedule_order])
    def __init__(self) -> None:
        raise NotImplementedError

    # PSEUDO:
    # - If request.trace_id is set AND request.confirm → resume_session(trace_id), continue to schedule_order.
    # - Else: new session. Feed request.text to the agent.
    # - Tool rounds: resolve_recipe (if ambiguous → emit disambiguation, await user pick); scale_recipe; check_inventory.
    # - Return proposal with status="awaiting_confirmation" + persisted trace_id.
    # - finally: record_outcome()
    async def run(self, request: NLOrderingRequest) -> NLOrderingResponse:
        raise NotImplementedError

    # PSEUDO:
    # - Load session state by trace_id (Phase 1: pickle in .claude/state/sessions/{trace_id}.pkl).
    # - Phase 2: durable session in Inngest event store.
    async def resume_session(self, trace_id: str) -> Any:
        raise NotImplementedError


# Phase 2 Graduation:
#   - Session resumption becomes durable via Inngest (today: pickle-on-disk). Seam: resume_session() body.
#   - check_inventory goes from stub to real ERP integration. Seam: agents/tools_sdk.py::check_inventory().
#   - Escalation (Haiku→Sonnet on repeated no-progress) already wired via ClaudeSDKClient config.
