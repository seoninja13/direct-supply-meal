---
name: Dietary rule precedence
description: Deterministic dietary-flag verdicts are law; LLM narrative reasoning is advisory.
type: feedback
---

# Dietary rule precedence

**Rule:** When `check_compliance` returns `status="fail"` for a recipe against any resident, the recipe MUST NOT appear in that meal slot for that facility's plan. Narrative reasoning from the Menu Planner agent is advisory; it never overrides a deterministic fail.

**Why:** Failure cases include allergen exposure, carbohydrate caps for diabetic residents, potassium/phosphorus caps for renal residents, and texture-level mismatches for dysphagia. Each of these carries real medical risk. A deterministic check codifies the risk; an LLM explanation narrates it.

**How to apply:**
- If any candidate recipe's verdict is `fail` → drop it from the candidate pool.
- If verdict is `warn` → allow it, include the warning narrative in the MealPlanSlot notes.
- If verdict is `pass` → no caveat.
- Aggregation rule for facility-level checks: a recipe "fails" for a facility if it fails for any resident; "warns" if ≥10% of residents.
