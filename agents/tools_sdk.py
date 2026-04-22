"""
agents/tools_sdk.py — MCP-shaped @tool wrappers for NL Ordering (Slice D).

Each function here wraps a pure helper from agents/tools.py or a service from
app/services/ and returns the MCP content shape the Claude Agent SDK expects:
    {"content": [{"type": "text", "text": "<json>"}], "isError": False}

Both plain (`TOOL_REGISTRY`) and SDK-decorated (`sdk_tool` versions via
`build_nl_ordering_mcp_server`) shapes are exposed so the driver can dispatch
via whichever is appropriate at the call site.

Menu-planner tools (check_compliance, estimate_cost, generate_meal_plan, etc.)
ship with Slice E.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from agents.tools import (
    db_find_existing_order,
    db_get_recipe,
    db_insert_order,
    db_resolve_recipe,
)


def _tool_success(data: dict[str, Any]) -> dict[str, Any]:
    """Return the MCP success envelope."""
    return {
        "content": [{"type": "text", "text": json.dumps(data)}],
        "isError": False,
    }


def _tool_error(
    code: str,
    message: str,
    hint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the MCP error envelope with a machine-parsable code."""
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if hint is not None:
        body["error"]["hint"] = hint
    return {
        "content": [{"type": "text", "text": json.dumps(body)}],
        "isError": True,
    }


async def resolve_recipe(args: dict[str, Any]) -> dict[str, Any]:
    """Fuzzy-resolve a recipe name against the catalog.

    Args: {"name_query": str, "top_k": int = 3, "min_confidence": float = 0.5}
    Success: {"candidates": [{id, title, confidence}], "count": N}
    Errors: invalid_input (missing name_query), no_match (empty candidates).
    """
    name_query = args.get("name_query")
    if not name_query or not isinstance(name_query, str):
        return _tool_error("invalid_input", "name_query is required (non-empty string)")

    top_k = int(args.get("top_k", 3))
    min_confidence = float(args.get("min_confidence", 0.5))

    candidates = await db_resolve_recipe(
        name_query, top_k=top_k, min_confidence=min_confidence
    )
    if not candidates:
        return _tool_error(
            "no_match",
            f"No recipe matched {name_query!r} above confidence {min_confidence}",
            hint={"suggestion": "relax the confidence threshold or ask the user"},
        )
    return _tool_success({"candidates": candidates, "count": len(candidates)})


async def scale_recipe(args: dict[str, Any]) -> dict[str, Any]:
    """Pure ingredient-gram scaling for a given recipe + target servings.

    Args: {"recipe_id": int, "n_servings": int}
    Success: {scale_factor, total_grams, ingredients: [...]}. See app.services.scaling.
    """
    try:
        recipe_id = int(args["recipe_id"])
        n_servings = int(args["n_servings"])
    except (KeyError, TypeError, ValueError):
        return _tool_error(
            "invalid_input",
            "recipe_id (int) and n_servings (int) are required",
        )

    recipe = await db_get_recipe(recipe_id)
    if recipe is None:
        return _tool_error(
            "recipe_not_found",
            f"No recipe with id={recipe_id}",
        )

    # Phase 1: the NL flow doesn't need the ingredient breakdown — it just
    # needs (recipe title, cost per serving, target n_servings). Scaling
    # ingredient grams is a pure helper the Menu Planner will call more
    # aggressively in Slice E. For Slice D we return the projected totals.
    total = recipe["cost_cents_per_serving"] * n_servings
    return _tool_success(
        {
            "recipe_id": recipe_id,
            "title": recipe["title"],
            "n_servings": n_servings,
            "unit_price_cents": recipe["cost_cents_per_serving"],
            "line_total_cents": total,
            "scale_factor": round(n_servings / max(1, recipe["base_yield"]), 3),
        }
    )


async def check_inventory(args: dict[str, Any]) -> dict[str, Any]:
    """Check ingredient availability for a proposed order (Phase 1 stub: always OK).

    Args: {"recipe_id": int, "n_servings": int, "needed_by": str (ISO date)}
    Success: {"status": "ok", "notes": "stub"}.

    Phase 2 Graduation: real supplier ERP call. Seam is this function body.
    """
    recipe_id = args.get("recipe_id")
    if recipe_id is None:
        return _tool_error("invalid_input", "recipe_id is required")
    return _tool_success(
        {
            "status": "ok",
            "recipe_id": recipe_id,
            "notes": "Phase 1 stub — inventory always available.",
        }
    )


async def schedule_order(args: dict[str, Any]) -> dict[str, Any]:
    """Persist the order when the user has confirmed the proposal.

    Args: {
        facility_id, placed_by_user_id, recipe_id, n_servings,
        unit_price_cents, delivery_date (ISO),
        delivery_window_slot?, notes?, confirmed: bool,
    }

    Success: {"order_id": N, "status": "pending", ...}.
    Errors: not_confirmed (confirmed != true), invalid_input, duplicate_order.
    """
    if not args.get("confirmed"):
        return _tool_error(
            "not_confirmed",
            "schedule_order refuses to persist without confirmed=true",
        )

    try:
        facility_id = int(args["facility_id"])
        placed_by_user_id = int(args["placed_by_user_id"])
        recipe_id = int(args["recipe_id"])
        n_servings = int(args["n_servings"])
        unit_price_cents = int(args["unit_price_cents"])
        delivery_date = date.fromisoformat(str(args["delivery_date"]))
    except (KeyError, TypeError, ValueError) as exc:
        return _tool_error(
            "invalid_input",
            f"missing or malformed field: {exc}",
        )

    existing = await db_find_existing_order(
        facility_id=facility_id,
        recipe_id=recipe_id,
        delivery_date=delivery_date,
    )
    if existing is not None:
        # Idempotent: return the existing order rather than creating a duplicate.
        return _tool_success(
            {
                "order_id": existing["id"],
                "status": existing["status"],
                "duplicate": True,
            }
        )

    order = await db_insert_order(
        facility_id=facility_id,
        placed_by_user_id=placed_by_user_id,
        recipe_id=recipe_id,
        n_servings=n_servings,
        unit_price_cents=unit_price_cents,
        delivery_date=delivery_date,
        delivery_window_slot=args.get("delivery_window_slot", "midday_11_1"),
        notes=args.get("notes"),
        pricing_source=args.get("pricing_source", "static"),
    )
    return _tool_success(
        {
            "order_id": order["id"],
            "status": order["status"],
            "total_cents": order["total_cents"],
            "duplicate": False,
        }
    )


# ---------------------------------------------------------------------------
# Tool registry — the NL Ordering driver looks up tools by name.
# Keys must match the strings the LLM uses in tool_use messages.
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, Any] = {
    "resolve_recipe": resolve_recipe,
    "scale_recipe": scale_recipe,
    "check_inventory": check_inventory,
    "schedule_order": schedule_order,
}


# ---------------------------------------------------------------------------
# Claude Agent SDK MCP tool wrappers — the production path.
#
# The plain async functions above are what the driver's test path calls
# directly. The SDK path below wraps those same functions with @tool so the
# Claude Agent SDK's MCP machinery can call them during a real agent session.
# ---------------------------------------------------------------------------


@tool(
    "resolve_recipe",
    "Fuzzy-match a free-text recipe name to the catalog. Returns up to top_k candidates above min_confidence.",
    {"name_query": str, "top_k": int, "min_confidence": float},
)
async def _sdk_resolve_recipe(args: dict[str, Any]) -> dict[str, Any]:
    return await resolve_recipe(args)


@tool(
    "scale_recipe",
    "Project cost + totals for a recipe at a target number of servings. Pure computation.",
    {"recipe_id": int, "n_servings": int},
)
async def _sdk_scale_recipe(args: dict[str, Any]) -> dict[str, Any]:
    return await scale_recipe(args)


@tool(
    "check_inventory",
    "Verify that ingredients are in stock for a proposed order (Phase 1 stub: always ok).",
    {"recipe_id": int, "n_servings": int, "needed_by": str},
)
async def _sdk_check_inventory(args: dict[str, Any]) -> dict[str, Any]:
    return await check_inventory(args)


@tool(
    "schedule_order",
    "Persist a single-line order. MUST be called with confirmed=true only AFTER the user approves the proposal.",
    {
        "facility_id": int,
        "placed_by_user_id": int,
        "recipe_id": int,
        "n_servings": int,
        "unit_price_cents": int,
        "delivery_date": str,
        "delivery_window_slot": str,
        "notes": str,
        "confirmed": bool,
    },
)
async def _sdk_schedule_order(args: dict[str, Any]) -> dict[str, Any]:
    return await schedule_order(args)


def build_nl_ordering_mcp_server():
    """Construct the in-process MCP server the SDK agent calls into.

    Returns a McpSdkServerConfig that slots into `ClaudeAgentOptions.mcp_servers`.
    """
    return create_sdk_mcp_server(
        name="ds_meal_nl_ordering",
        version="0.1.0",
        tools=[
            _sdk_resolve_recipe,
            _sdk_scale_recipe,
            _sdk_check_inventory,
            _sdk_schedule_order,
        ],
    )


# All 4 tool names the SDK-side agent is allowed to call. Matches the
# registrations in build_nl_ordering_mcp_server(). Exposed so the driver
# can pass them to `ClaudeAgentOptions.allowed_tools` verbatim.
NL_ORDERING_TOOL_NAMES: tuple[str, ...] = (
    "mcp__ds_meal_nl_ordering__resolve_recipe",
    "mcp__ds_meal_nl_ordering__scale_recipe",
    "mcp__ds_meal_nl_ordering__check_inventory",
    "mcp__ds_meal_nl_ordering__schedule_order",
)


__all__ = [
    "NL_ORDERING_TOOL_NAMES",
    "TOOL_REGISTRY",
    "build_nl_ordering_mcp_server",
    "check_inventory",
    "resolve_recipe",
    "scale_recipe",
    "schedule_order",
]


# Phase 2 Graduation:
#   - Add the 5 menu-planner tools in Slice E.
#   - Swap `check_inventory` stub for a real supplier ERP call.
