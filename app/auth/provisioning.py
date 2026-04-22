"""
PSEUDOCODE:
1. One-line summary of module purpose.
   - First-time sign-in provisioning: verify the Clerk JWT, look up a Facility by
     admin_email, INSERT a User row linking clerk_user_id to facility_id. Gate the
     allowlist here and at the Clerk webhook so bypass is impossible (P15).
2. Ordered steps.
   a. provision_user(claims, session) is called from the /sign-in/callback route.
   b. Look up existing User by clerk_user_id — if present, return it (idempotent).
   c. Else look up Facility row where admin_email = claims.email.
        - 0 matches → raise NotOnAllowlist (maps to 403 in the route).
        - ≥1 matches → pick the first (Phase 1 invariant: one facility per admin email).
   d. INSERT user(clerk_user_id, email, facility_id, role="admin").
   e. Return the new User row.
   f. Phase 2 seam: handle Clerk webhook user.created asynchronously for durable provisioning.
3. Inputs / Outputs.
   - Inputs: ClerkClaims (from verify_clerk_jwt), SQLModel session.
   - Outputs: User ORM row bound to a Facility. NotOnAllowlist exception on mismatch.
4. Side effects.
   - INSERT on the user table (first sign-in only).
   - No network calls beyond the JWT verify (which happens upstream in the route).

IMPLEMENTATION: Phase 4 — see functions below.
"""

from __future__ import annotations


class NotOnAllowlist(Exception):
    # PSEUDO: Raised when the claim email is not in any Facility.admin_email row.
    #   Route maps this to HTTPException(403, "not_on_allowlist") and renders a friendly page.
    pass


def provision_user(claims, session):
    # PSEUDO: Idempotent provisioning.
    #   1. existing = session.exec(select(User).where(clerk_user_id == claims.sub)).first().
    #        If existing: return existing (short-circuit).
    #   2. facility = session.exec(
    #           select(Facility).where(Facility.admin_email == claims.email)
    #       ).first().
    #        If facility is None: raise NotOnAllowlist(claims.email).
    #   3. user = User(
    #           clerk_user_id=claims.sub,
    #           email=claims.email,
    #           facility_id=facility.id,
    #           role="admin",
    #       ).
    #   4. session.add(user); session.commit(); session.refresh(user).
    #   5. Log a single line to logs/auth.log: "provisioned user=<email> facility=<name>".
    #   6. Return user.
    raise NotImplementedError


def handle_clerk_webhook(event: dict, session) -> None:
    # PSEUDO: Secondary provisioning path invoked by the Clerk `user.created` webhook.
    #   1. Verify Svix signature (request headers) — out of scope here, done in the route.
    #   2. Extract primary_email_address + clerk_user_id from the event payload.
    #   3. Build a synthetic ClerkClaims dataclass and call provision_user().
    #   4. Catch NotOnAllowlist → respond 403 so Clerk retries do not loop.
    raise NotImplementedError


# Phase 2 Graduation: move provisioning to an Inngest-handled webhook queue so flaky INSERTs
# retry durably; extend provision_user() to honour org-scoped roles (admin / dietitian / kitchen)
# when Clerk Organizations replace the single-admin allowlist.
