"""
PSEUDOCODE:
1. Insert 20–30 hand-authored synthetic rows into the agent_trace SQLite table.
2. Realistic Riverside SNF patterns: staff typing "oats" for Overnight Oats, "tomorrow morning" for morning_6_8 slot, etc.
3. Each row: agent_name, query_text, tool_calls_json, outcome, confidence_score, latency_ms, cost_cents, notes.
4. Disclosed as a seed — NOT hidden. Purpose is to bootstrap the Karpathy compile on demo day.
5. Inputs: none (hardcoded list in this script).
6. Outputs: appended rows in agent_trace table.
7. Side effects: DB writes. Idempotent check: skip if any row with matching (agent_name, query_text) exists.

IMPLEMENTATION: Phase 4.

Rationale: docs/workflows/KARPATHY-AUTO-RESEARCH-WORKFLOW.md §11 (Phase 1 honesty).
"""


# from app.db.database import get_sync_session


SEED_TRACES = [
    # nl_ordering seeds — ~20 rows covering aliases, meal-type shorthands, portion shorthands
    # Example (Phase 4 fills in full list):
    # {
    #   "agent_name": "nl_ordering",
    #   "query_text": "40 oats for tomorrow morning",
    #   "tool_calls_json": '[{"tool":"resolve_recipe","args":{"name_query":"oats"},"result":"Overnight Oats, score=0.62"},{"tool":"clarify","args":{"candidates":3},"result":"user_picked=Overnight Oats"},{"tool":"schedule_order","args":{"recipe_id":3,"servings":40,"service_date":"2026-04-23"},"result":"order_id=221"}]',
    #   "outcome": "disambiguation",
    #   "confidence_score": 0.62,
    #   "latency_ms": 3200,
    #   "cost_cents": 1,
    #   "notes": "Staff used 'oats' shorthand for Overnight Oats; required disambiguation"
    # },
    # ... ~20 nl_ordering rows
    # ... ~10 menu_planner rows showing common dietary-mix patterns
]


# PSEUDO:
# - open sync session
# - for trace in SEED_TRACES: skip if exists; else INSERT
# - print "Seeded N traces"
def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()


# Phase 2 Graduation:
#   - Retire this script when organic traffic exceeds 200 traces/agent over 14 days.
#     Seam: move file to scripts/archive/.
