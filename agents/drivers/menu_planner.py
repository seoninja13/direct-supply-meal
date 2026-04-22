"""
PSEUDOCODE:
1. Menu Planner L1 Director — Sonnet, stateful ClaudeSDKClient, multi-turn.
2. Given facility_id + week_start + dietary census + budget + headcount, build a 7-day menu (21 slots) that passes compliance and lands within budget.
3. Typical 6-round tool flow: search_recipes x2 → check_compliance x3 → estimate_cost x1 → save_menu x1.
4. Session-start hook (`.claude/hooks/wiki_session_inject.py`) prepends relevant wiki topic pages into the system prompt.
5. Inputs: MenuPlannerRequest pydantic model.
6. Outputs: {meal_plan_id, days, total_cost_cents, warnings, source}.
7. Side effects: writes MealPlan + 21 MealPlanSlot rows; writes agent_trace row on finally.

IMPLEMENTATION: Phase 4.

Contract: docs/workflows/AGENT-WORKFLOW.md §3.
"""

from dataclasses import dataclass
from typing import Any

# from claude_agent_sdk import ClaudeSDKClient
# from agents.observability import record_outcome
# from agents.tools_sdk import (
#     search_recipes, check_compliance, estimate_cost, save_menu,
# )
# from agents.depth_scorer import score_query
# from app.services.menu_fallback import generate_fallback_menu


@dataclass
class MenuPlannerRequest:
    facility_id: int
    week_start: str  # ISO date
    budget_cents: int
    headcount: int
    census: dict[str, int]  # flag → count


@dataclass
class MenuPlannerResponse:
    meal_plan_id: int | None
    days: list[dict[str, Any]]
    total_cost_cents: int
    warnings: list[str]
    source: str  # "llm" | "static_fallback"


class MenuPlannerDirector:
    # PSEUDO:
    # - __init__: load agents/prompts/menu_planner.md; ClaudeSDKClient(
    #     model="claude-sonnet-4-5", retry=3, escalation=False, max_turns=12,
    #     per_turn_deadline_ms=45000, session_deadline_ms=180000,
    #     tools=[search_recipes, check_compliance, estimate_cost, save_menu])
    def __init__(self) -> None:
        raise NotImplementedError

    # PSEUDO:
    # - trace = start_trace("menu_planner", request)
    # - try:
    #     - level, n_agents, _ = score_query(describe(request))
    #     - log trace.depth_level
    #     - open ClaudeSDKClient session
    #     - call session.query(build_user_turn(request))
    #     - loop turns until session.done or save_menu fired
    #     - collect tool outcomes; if LLM unreachable → fall back to generate_fallback_menu()
    # - finally: record_outcome(trace)
    # - return MenuPlannerResponse(...)
    async def run(self, request: MenuPlannerRequest) -> MenuPlannerResponse:
        raise NotImplementedError


# Phase 2 Graduation:
#   - dispatch() body swaps sync for Inngest (see agents/drivers/dispatch.py).
#   - Depth-score >=7 actually decomposes (today: logs only) — seam in agents/depth_scorer.py.
#   - Wiki injection gets richer once MiniLM embeddings replace hand-clustering — seam in wiki/compiler.py::cluster_traces().
