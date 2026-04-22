---
name: Riverside SNF census
description: The single facility with admin_email in Phase 1. 120 beds, skilled-nursing, rich dietary mix.
type: project
---

# Riverside SNF — census profile

**120-bed skilled-nursing facility.** The only facility in Phase 1 whose `admin_email` is set (`admin@dulocore.com`). All demo sign-ins bind to this facility.

**Approximate dietary mix** (seeded in `fixtures/residents.json`):
- ~40% diabetic
- ~35% low-sodium
- ~25% renal
- ~25% pureed / soft-food
- Allergens scattered individually: nuts (~8%), dairy (~12%), gluten (~6%), shellfish (~3%), egg (~5%).

**Why this matters:** the compliance checker gets real work to do on this facility. A menu that passes for Harbor View (Independent Living, 150 beds, minimal dietary restrictions) would fail for Riverside. Interviewers see the compliance narrative fire on real resident profiles, not toy ones.

**Phase 2:** additional admin_emails on other facilities unlock multi-tenant demo; this file stays as the baseline example.
