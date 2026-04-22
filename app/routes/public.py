"""
PSEUDOCODE:
1. Public (no-auth) routes: /, /health, /sign-in, /sign-in/callback, /sign-out.
2. / renders landing page with "Sign in to order" CTA.
3. /health returns {"status":"ok"} — liveness for Docker HEALTHCHECK and Traefik loadbalancer.healthcheck.
4. /sign-in 302s to the Clerk-hosted OAuth page.
5. /sign-in/callback verifies the JWT via JWKS middleware, provisions the User row, redirects to /facility/dashboard.
6. /sign-out clears the Clerk cookie, redirects to /.
7. Every HTML route has a 1:1 /api/v1/ JSON twin where applicable (Frontend/Backend Decoupling rule, P14).

IMPLEMENTATION: Phase 4.

Contract: docs/workflows/DOMAIN-WORKFLOW.md §4 (J2 sign-in), PROTOCOL-APPLICATION-MATRIX.md P14 + P15.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

router = APIRouter()
api_router = APIRouter(prefix="/api/v1")


# PSEUDO: render templates/landing.html with {page_title:"ds-meal"}
@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    raise NotImplementedError


# PSEUDO: return {"status":"ok","service":"ds-meal"}. No DB access.
@router.get("/health")
async def health_html():
    raise NotImplementedError


@api_router.get("/health")
async def health_json():
    # PSEUDO: same as above; kept separate so OpenAPI schema lists it under /api/v1.
    raise NotImplementedError


# PSEUDO: 302 redirect to Clerk's hosted sign-in URL from settings.CLERK_SIGN_IN_URL.
@router.get("/sign-in")
async def sign_in_redirect():
    raise NotImplementedError


# PSEUDO:
# - receive Clerk callback with session JWT
# - verify via app.auth.clerk_middleware.verify_clerk_jwt
# - call app.auth.provisioning.provision_or_load_user(claims)
# - if not allowlisted → 403 HTMLResponse "Access denied"
# - else set session cookie, redirect to /facility/dashboard
@router.get("/sign-in/callback")
async def sign_in_callback(request: Request):
    raise NotImplementedError


# PSEUDO: clear Clerk cookie, redirect to /.
@router.post("/sign-out")
async def sign_out():
    raise NotImplementedError


# Phase 2 Graduation:
#   - /sign-in 302 target becomes a multi-tenant router choosing Clerk instance by subdomain.
#   - /sign-in/callback grows role assignment beyond the single-admin allowlist.
