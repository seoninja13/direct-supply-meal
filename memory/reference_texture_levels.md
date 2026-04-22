---
name: Texture levels (IDDSI-inspired)
description: The 0–4 integer texture_level stored on each Recipe and required by compliance.py soft_food / pureed rules.
type: reference
---

# Texture levels — IDDSI-inspired 0–4 scale

ds-meal uses a compressed integer texture scale inspired by the International Dysphagia Diet Standardisation Initiative (IDDSI). It is NOT a medical-grade IDDSI implementation.

| Level | Name              | Description                                    | Example recipes                    |
|-------|-------------------|------------------------------------------------|------------------------------------|
| 0     | Regular           | Normal texture; no modification                | Chicken Stir-Fry, Veggie Omelette  |
| 1     | Soft              | Easy to chew; moist; small pieces              | Overnight Oats, Lentil Soup        |
| 2     | Mechanical-soft   | Ground or mashed; cohesive                     | Beef Stew, Shepherd's Pie          |
| 3     | Minced & moist    | Finely minced; gravy/sauce required            | Turkey Meatloaf (minced variant)   |
| 4     | Pureed            | Smooth, uniform consistency; no lumps          | Pureed Chicken + Sweet Potato      |

**Compliance rules that consume this:**
- `check_soft_food` requires `texture_level ≤ 2`.
- `check_pureed` requires `texture_level ≤ 1`.
- `check_mechanical_soft` (not implemented in Phase 1 — Phase 2 seam) requires `texture_level ≤ 2`.

Each Recipe row carries `texture_level` as an integer. Menu Planner filters candidates by this value when a facility census includes `soft_food` or `pureed` flags.
