"""
PSEUDOCODE:
1. Purpose: Two pricing paths in one module (DOMAIN-WORKFLOW.md
   Section 6). static_rollup() is pure and drives browsing routes;
   estimate_cost() is a hybrid that overlays a Haiku-refined price on
   the static baseline, with a conservative guardrail that falls back
   to static on any LLM error or >30% deviation.
2. Ordered algorithm:
   - static_rollup:
       a. Load Recipe(recipe_id).
       b. per_serving_cents = recipe.cost_cents_per_serving.
       c. total_cents       = per_serving_cents * n_servings.
       d. Return {per_serving_cents, total_cents}.
   - estimate_cost:
       a. baseline = static_rollup(recipe_id, n_servings).
       b. Build a Haiku prompt including baseline + context
          (facility size, bulk-scale hint, season).
       c. Call claude_agent_sdk.query(model=HAIKU) with that prompt.
       d. Parse refined per_serving_cents + reasoning from output.
       e. deviation = abs(refined - baseline.per_serving) /
                       baseline.per_serving
          if deviation > PRICING_LLM_DEVIATION_MAX or parse fails
             or any exception from the SDK:
               return {**baseline, reasoning: fallback_reason,
                       source: "static"}
          else:
               return {per_serving_cents: refined,
                       total_cents: refined * n_servings,
                       reasoning: llm_reasoning,
                       source: "llm_refined"}
3. Inputs / Outputs:
   - static_rollup(recipe_id:int, n_servings:int) ->
       {per_serving_cents:int, total_cents:int}
   - estimate_cost(recipe_id:int, n_servings:int, context:dict) ->
       {per_serving_cents:int, total_cents:int,
        reasoning:str, source: "static"|"llm_refined"}
4. Side effects:
   - static_rollup: one SELECT of Recipe.
   - estimate_cost: one SELECT + one outbound LLM call (Haiku).
     Never writes. The source value is persisted on OrderLine by the
     caller (services/orders.py) so pricing origin is auditable.

IMPLEMENTATION: Phase 4.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

PRICING_LLM_DEVIATION_MAX: float = 0.30  # >30% refinement => fallback


class StaticRollup(TypedDict):
    per_serving_cents: int
    total_cents: int


class EstimateResult(TypedDict):
    per_serving_cents: int
    total_cents: int
    reasoning: str
    source: Literal["static", "llm_refined"]


def static_rollup(recipe_id: int, n_servings: int) -> StaticRollup:
    # PSEUDO:
    #   1. if n_servings <= 0: raise ValueError
    #   2. recipe = load Recipe(recipe_id)                 # app.models.recipe
    #   3. per_serving = recipe.cost_cents_per_serving
    #   4. total       = per_serving * n_servings
    #   5. return {"per_serving_cents": per_serving,
    #              "total_cents": total}
    raise NotImplementedError("Phase 4")


def _build_prompt(
    recipe: Any, n_servings: int, baseline: StaticRollup, context: dict
) -> str:
    # PSEUDO:
    #   Construct a short, structured Haiku prompt:
    #     - static baseline (per_serving_cents, total_cents)
    #     - recipe title + ingredients summary
    #     - context: facility_name, bed_count, season, bulk_hint
    #     - ask for JSON {per_serving_cents:int, reasoning:str}
    raise NotImplementedError("Phase 4")


def _call_haiku(prompt: str) -> dict:
    # PSEUDO:
    #   Invoke claude_agent_sdk.query(prompt, model=HAIKU).
    #   Expect structured JSON output.
    #   On AnthropicAPIError/AuthError/429/parse error:
    #     raise a caller-friendly PricingLLMError (caught by
    #     estimate_cost which falls back to static).
    raise NotImplementedError("Phase 4")


def estimate_cost(
    recipe_id: int, n_servings: int, context: dict
) -> EstimateResult:
    # PSEUDO:
    #   1. baseline = static_rollup(recipe_id, n_servings)
    #   2. try:
    #        recipe = load Recipe(recipe_id)
    #        prompt = _build_prompt(recipe, n_servings, baseline, context)
    #        parsed = _call_haiku(prompt)
    #        refined = int(parsed["per_serving_cents"])
    #        reasoning = str(parsed["reasoning"])
    #      except Exception:
    #        return {**baseline,
    #                "reasoning": "LLM unavailable; static baseline used.",
    #                "source": "static"}
    #   3. deviation = abs(refined - baseline["per_serving_cents"]) /
    #                  max(baseline["per_serving_cents"], 1)
    #      if deviation > PRICING_LLM_DEVIATION_MAX:
    #          return {**baseline,
    #                  "reasoning": f"LLM refinement {deviation:.0%} "
    #                               "exceeded guardrail; static baseline used.",
    #                  "source": "static"}
    #   4. return {"per_serving_cents": refined,
    #              "total_cents":       refined * n_servings,
    #              "reasoning":         reasoning,
    #              "source":            "llm_refined"}
    raise NotImplementedError("Phase 4")


# Phase 2 Graduation: services/pricing.py::estimate_cost() — replace
# static_rollup body with a supplier ERP sync fetching real unit costs;
# estimate_cost contract stays the same so the agent surface is stable.
