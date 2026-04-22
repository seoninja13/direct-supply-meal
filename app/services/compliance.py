"""
PSEUDOCODE:
1. Purpose: Deterministic dietary-compliance evaluation for a Recipe
   against either a single Resident or an entire Facility census.
   Implements the 6 rules from DOMAIN-WORKFLOW.md Section 5. Every
   rule returns a structured verdict the Menu Planner LLM wraps in
   narrative — the LLM may advise, never override.
2. Ordered algorithm:
   a. Per-rule check_* functions each return a RuleResult with
      verdict in {"pass", "warn", "fail"}.
   b. check_compliance() looks up resident.dietary_flags, runs the
      matching rules, and returns the worst verdict with a per-rule
      breakdown.
   c. check_compliance_facility() iterates over all residents at a
      facility, calls check_compliance per resident, and rolls up:
         - fail if any resident fails
         - warn if >=10% of residents warn
         - else pass.
3. Inputs / Outputs:
   - check_* rule inputs: Recipe + Resident rows.
   - Aggregators take ids, load rows from DB (Phase 4), return dict.
4. Side effects: Read-only DB access (aggregator functions). No
   writes. No LLM calls — this is the deterministic layer beneath
   the Menu Planner agent.

IMPLEMENTATION: Phase 4.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

Verdict = Literal["pass", "warn", "fail"]

# Deterministic rule caps — DOMAIN-WORKFLOW.md Section 5.
DIABETIC_CARBS_CAP_G: int = 60
DIABETIC_WARN_PCT: float = 0.10
LOW_SODIUM_CAP_MG: int = 600
LOW_SODIUM_WARN_PCT: float = 0.15
RENAL_POTASSIUM_CAP_MG: int = 800
RENAL_PHOSPHORUS_CAP_MG: int = 250
RENAL_WARN_PCT: float = 0.10
SOFT_FOOD_TEXTURE_MAX: int = 2
PUREED_TEXTURE_MAX: int = 1
FACILITY_WARN_RESIDENT_PCT: float = 0.10


class RuleResult(TypedDict, total=False):
    verdict: Verdict
    rule: str
    actual: Any
    cap: Any
    matched_allergens: list[str]


class ComplianceResult(TypedDict):
    verdict: Verdict
    rules: list[RuleResult]


class FacilityComplianceResult(TypedDict):
    verdict: Verdict
    resident_count: int
    failing_resident_ids: list[int]
    warning_resident_ids: list[int]
    per_resident: list[dict]


def check_diabetic(recipe: Any, resident: Any) -> RuleResult:
    # PSEUDO:
    #   cap  = getattr(resident, "max_carbs_per_meal", DIABETIC_CARBS_CAP_G)
    #   carb = recipe.carbs_g
    #   if carb > cap:                    verdict = "fail"
    #   elif carb >= cap * (1 - DIABETIC_WARN_PCT): verdict = "warn"
    #   else:                             verdict = "pass"
    #   return {"verdict": verdict, "rule": "diabetic",
    #           "actual": carb, "cap": cap}
    raise NotImplementedError("Phase 4")


def check_low_sodium(recipe: Any, resident: Any) -> RuleResult:
    # PSEUDO:
    #   cap = LOW_SODIUM_CAP_MG
    #   na  = recipe.sodium_mg
    #   if na > cap:                                verdict = "fail"
    #   elif na >= cap * (1 - LOW_SODIUM_WARN_PCT): verdict = "warn"
    #   else:                                       verdict = "pass"
    #   return {"verdict": v, "rule": "low_sodium",
    #           "actual": na, "cap": cap}
    raise NotImplementedError("Phase 4")


def check_renal(recipe: Any, resident: Any) -> RuleResult:
    # PSEUDO:
    #   k = recipe.potassium_mg
    #   p = recipe.phosphorus_mg
    #   if k > RENAL_POTASSIUM_CAP_MG or p > RENAL_PHOSPHORUS_CAP_MG:
    #       verdict = "fail"
    #   elif (k >= RENAL_POTASSIUM_CAP_MG * (1 - RENAL_WARN_PCT)
    #         or p >= RENAL_PHOSPHORUS_CAP_MG * (1 - RENAL_WARN_PCT)):
    #       verdict = "warn"
    #   else:
    #       verdict = "pass"
    #   return {"verdict": verdict, "rule": "renal",
    #           "actual": {"potassium_mg": k, "phosphorus_mg": p},
    #           "cap": {"potassium_mg": RENAL_POTASSIUM_CAP_MG,
    #                   "phosphorus_mg": RENAL_PHOSPHORUS_CAP_MG}}
    raise NotImplementedError("Phase 4")


def check_soft_food(recipe: Any, resident: Any) -> RuleResult:
    # PSEUDO:
    #   t = recipe.texture_level
    #   verdict = "fail" if t > SOFT_FOOD_TEXTURE_MAX else "pass"
    #   return {"verdict": verdict, "rule": "soft_food",
    #           "actual": t, "cap": SOFT_FOOD_TEXTURE_MAX}
    raise NotImplementedError("Phase 4")


def check_pureed(recipe: Any, resident: Any) -> RuleResult:
    # PSEUDO:
    #   t = recipe.texture_level
    #   verdict = "fail" if t > PUREED_TEXTURE_MAX else "pass"
    #   return {"verdict": verdict, "rule": "pureed",
    #           "actual": t, "cap": PUREED_TEXTURE_MAX}
    raise NotImplementedError("Phase 4")


def check_allergens(recipe: Any, resident: Any) -> RuleResult:
    # PSEUDO:
    #   recipe_set   = set(recipe.allergens or [])
    #   resident_set = set(resident.allergen_flags or [])
    #   matched      = sorted(recipe_set & resident_set)
    #   verdict      = "fail" if matched else "pass"
    #   return {"verdict": verdict, "rule": "allergens",
    #           "matched_allergens": matched}
    raise NotImplementedError("Phase 4")


def _worst(verdicts: list[Verdict]) -> Verdict:
    # PSEUDO:
    #   order = {"pass": 0, "warn": 1, "fail": 2}
    #   return max(verdicts, key=lambda v: order[v]) if verdicts else "pass"
    raise NotImplementedError("Phase 4")


def check_compliance(
    recipe_id: int, resident_profile_id: int
) -> ComplianceResult:
    # PSEUDO:
    #   1. recipe   = load Recipe(recipe_id) from DB           # app.models.recipe
    #   2. resident = load Resident(resident_profile_id)
    #                 with .dietary_flags eager                # app.models.resident
    #   3. results = []
    #      flag_to_rule = {
    #        "diabetic":   check_diabetic,
    #        "low_sodium": check_low_sodium,
    #        "renal":      check_renal,
    #        "soft_food":  check_soft_food,
    #        "pureed":     check_pureed,
    #      }
    #      for flag in resident.dietary_flags:
    #          fn = flag_to_rule.get(flag.flag)
    #          if fn: results.append(fn(recipe, resident))
    #      # allergen check runs whenever resident has any allergen flag
    #      if resident.allergen_flags:
    #          results.append(check_allergens(recipe, resident))
    #   4. worst = _worst([r["verdict"] for r in results]) or "pass"
    #   5. return {"verdict": worst, "rules": results}
    raise NotImplementedError("Phase 4")


def check_compliance_facility(
    recipe_id: int, facility_id: int
) -> FacilityComplianceResult:
    # PSEUDO:
    #   1. residents = SELECT Resident WHERE facility_id = facility_id
    #   2. per_resident = []
    #      failing, warning = [], []
    #      for r in residents:
    #          res = check_compliance(recipe_id, r.id)
    #          per_resident.append({"resident_id": r.id, **res})
    #          if res["verdict"] == "fail": failing.append(r.id)
    #          elif res["verdict"] == "warn": warning.append(r.id)
    #   3. total = len(residents)
    #      if failing:
    #          verdict = "fail"
    #      elif total and (len(warning) / total) >= FACILITY_WARN_RESIDENT_PCT:
    #          verdict = "warn"
    #      else:
    #          verdict = "pass"
    #   4. return FacilityComplianceResult(
    #        verdict=verdict, resident_count=total,
    #        failing_resident_ids=failing,
    #        warning_resident_ids=warning,
    #        per_resident=per_resident,
    #      )
    raise NotImplementedError("Phase 4")


# Phase 2 Graduation: services/compliance.py rule functions — add
# machine-learned renal risk score and per-resident user-tunable cap
# overrides; plug in behind the same RuleResult contract so the
# Menu Planner agent surface stays unchanged.
