---
name: Demo admin preferences
description: admin@dulocore.com is the sole Phase 1 sign-in identity, bound to Riverside SNF.
type: user
---

# Demo admin — admin@dulocore.com

**Identity:** `admin@dulocore.com` (Ivan Dachev)
**Bound to:** Riverside SNF (120-bed skilled nursing)
**Clerk tenant:** `ds-meal-prototype` (Development instance, Google provider only)
**Role:** `admin`

**Allowlist enforcement:** the `/sign-in/callback` provisioning step looks up `Facility` by `admin_email`. Only `Riverside SNF` has this email set in `fixtures/facilities.json`. Any other Google email returns 403 with message "Access denied — contact your facility administrator."

**Demo behavior to expect:**
- First sign-in creates a `User` row linking `clerk_user_id` to `facility_id=riverside-snf`.
- Landing redirect goes to `/facility/dashboard`.
- All gated routes scope to this facility only — attempts to open orders from other facilities return 403 via `require_login`.

**Phase 2 Graduation:** multi-admin per facility + multi-facility per admin via role table. Seam: `app/auth/dependencies.py::require_login` extends to `require_role(role)`.
