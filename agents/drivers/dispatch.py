"""
PSEUDOCODE:
1. Single entry point for the FastAPI routes to invoke a Director.
2. Phase 1: synchronous in-process call — resolve the Director class by name, instantiate, call .run(payload).
3. Phase 2 seam: swap body to publish an Inngest event `director.invoked` with the payload, await the completion event.
4. Inputs: director_name (str, e.g. "menu_planner" | "nl_ordering"), payload (dict).
5. Outputs: director response dict (opaque to caller).
6. Side effects: delegate to driver which writes agent_trace row.

IMPLEMENTATION: Phase 4.
"""

from typing import Any


# PSEUDO:
# - Look up director class in a local registry dict {"menu_planner": MenuPlannerDirector, "nl_ordering": NLOrderingDirector}.
# - director = cls()
# - return await director.run(payload)
# - Phase 2 seam: this whole body becomes `return await inngest.send_and_await("director.invoked", {name, payload})`.
async def invoke_director(director_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError


# Phase 2 Graduation:
#   - Body of invoke_director() swaps from sync dispatch to Inngest event emit.
#   - Signature stays identical. Routes never know about the transport.
