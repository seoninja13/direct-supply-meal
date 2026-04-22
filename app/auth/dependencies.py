"""
PSEUDOCODE:
1. One-line summary of module purpose.
   - FastAPI dependency helpers: require_login loads the User row bound to the Clerk session,
     asserts facility-scope on resources, and raises 403 on mismatch (P15).
2. Ordered steps.
   a. _extract_token(request) — pull JWT from `Authorization: Bearer …` or the Clerk session
      cookie `__session` (fallback when the browser posts with cookies only).
   b. require_login(request, session) — verify JWT, load User by clerk_user_id,
      return a CurrentUser dataclass holding user_id, clerk_user_id, email, facility_id.
      Raise 401 if no token / invalid token; raise 403 if User row missing (not provisioned).
   c. require_facility_access(resource_facility_id, user=Depends(require_login)) — compare
      resource_facility_id to user.facility_id; raise 403 on mismatch. Used by every gated
      route that loads a facility-scoped record (Order, MealPlan, Resident).
   d. Phase 2 seam: require_role(role) factory that extends require_login with a role check.
3. Inputs / Outputs.
   - Inputs: fastapi.Request, SQLModel session (via Depends), Clerk JWT from header/cookie.
   - Outputs: CurrentUser instance injected into handlers. Raises HTTPException on failure.
4. Side effects.
   - One DB SELECT per gated request (user by clerk_user_id). No writes here.

IMPLEMENTATION: Phase 4 — see functions below.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CurrentUser:
    # PSEUDO: Typed projection passed to handlers; avoid leaking the full ORM row.
    user_id: int
    clerk_user_id: str
    email: str
    facility_id: int


def _extract_token(request) -> str:
    # PSEUDO: Pull the JWT from the request.
    #   1. Check request.headers.get("Authorization"); if it starts with "Bearer ", return the rest.
    #   2. Else check request.cookies.get("__session") (Clerk sets this during first-party sessions).
    #   3. If neither present, raise HTTPException(401, "missing_token").
    raise NotImplementedError


def require_login(request, session):
    # PSEUDO: FastAPI Depends entry point — returns a CurrentUser or raises.
    #   1. token = _extract_token(request).
    #   2. claims = verify_clerk_jwt(token)  # from clerk_middleware, raises AuthError on fail.
    #        Map AuthError -> HTTPException(401, "invalid_token").
    #   3. Query: SELECT * FROM user WHERE clerk_user_id = :claims.sub. Use injected `session`.
    #   4. If no row: raise HTTPException(403, "not_provisioned"). (Provisioning runs at
    #        /sign-in/callback; a missing row here means either first-sign-in bypassed callback
    #        OR the user's email is not in any Facility.admin_email allowlist.)
    #   5. Return CurrentUser(user_id=row.id, clerk_user_id=row.clerk_user_id,
    #        email=row.email, facility_id=row.facility_id).
    raise NotImplementedError


def require_facility_access(resource_facility_id: int, user: CurrentUser) -> CurrentUser:
    # PSEUDO: Tenancy guard. Called inside route handlers after loading a facility-scoped record.
    #   1. If user.facility_id != resource_facility_id: raise HTTPException(403, "cross_facility").
    #   2. Else return user (chainable for typed handlers).
    raise NotImplementedError


# Phase 2 Graduation: add require_role(role: str) factory that wraps require_login and checks a
# role claim (or a user_role row) before returning CurrentUser — seam for multi-tenant RBAC.
