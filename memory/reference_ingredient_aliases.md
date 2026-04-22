---
name: Ingredient & recipe aliases (seed)
description: Starting aliases the NL Ordering agent should resolve confidently without clarification turns.
type: reference
---

# Ingredient & recipe aliases (Phase 1 seed)

Staff at senior-care facilities use institutional shorthand. The NL Ordering agent's wiki page (`wiki/topics/nl_ordering/recipe-aliases.md`) grows organically from live traces, but this seed bootstraps the demo.

| Staff shorthand | Canonical recipe              | Facility context           |
|-----------------|-------------------------------|----------------------------|
| "oats"          | Overnight Oats                | Any, always breakfast slot |
| "eggs"          | Veggie Omelette               | Default omelette, not scrambled |
| "stew"          | Beef Stew                     | Unless "lentil" or "veggie" qualifier |
| "the soft one"  | Pureed Chicken + Sweet Potato | Memory care / dysphagia residents |
| "cod"           | Baked Cod + Rice              | Any |

**Rule:** if input matches an alias above AND has no additional recipe-qualifying noun, resolve directly with `confidence ≥ 0.85`. Confirm only quantity + delivery window.

**Counter-examples:** "oats and berries parfait" is a two-noun phrase → call `search_recipes`, don't bind to oats alias.
