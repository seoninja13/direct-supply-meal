# direct-supply-meal — Memory Index

Agent-consumable memory system. Five seed files cover the demo-critical facts. Phase 2 graduates to richer, Wiki-compiled memory — see `docs/workflows/KARPATHY-AUTO-RESEARCH-WORKFLOW.md`.

## Feedback (agent behavioral rules)
- [Dietary rule precedence](feedback_dietary_rules.md) — Fail > Warn > Pass. LLM narrative never overrides a deterministic fail.

## Project (ongoing context)
- [Riverside SNF census](project_facility_census.md) — 120-bed SNF; only facility with admin_email set.

## Reference (lookups)
- [Ingredient aliases](reference_ingredient_aliases.md) — Seed aliases the NL Ordering agent should resolve without clarification.
- [Texture levels](reference_texture_levels.md) — IDDSI-inspired 0–4 mapping used by compliance.py and Recipe.texture_level.

## User (demo identity)
- [Admin preferences](user_admin_preferences.md) — admin@dulocore.com is the sole allowlisted account, bound to Riverside SNF.

---

Phase 2 Graduation: this file is maintained by hand in Phase 1. Phase 2 merges the
compiled wiki (`wiki/topics/`) with this memory directory via a unified TOPICS-INDEX.
