"""
agents/drivers/dispatch.py — single entry point for FastAPI routes to invoke a Director.

Phase 1: in-process dispatch via a driver-class registry.
Phase 2 seam: body becomes `return await inngest.send_and_await("director.invoked", ...)`.
"""

from __future__ import annotations

from typing import Any

from agents.drivers.nl_ordering import NLOrderingDriver, NLOrderingRequest


async def invoke_director(
    director_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Resolve `director_name` to a driver class, call `.run(request)`, return dict."""
    if director_name == "nl_ordering":
        request = NLOrderingRequest(
            text=str(payload.get("text", "")),
            user_id=int(payload["user_id"]),
            facility_id=int(payload["facility_id"]),
            trace_id=payload.get("trace_id"),
            confirm=bool(payload.get("confirm", False)),
        )
        driver = NLOrderingDriver(query_fn=payload.get("query_fn"))
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

    # Slice E will add "menu_planner" here.
    raise ValueError(f"unknown director: {director_name}")


# Phase 2 Graduation:
#   - Body swaps from sync dispatch to Inngest event emit.
#   - Signature stays identical; routes never learn about the transport.
