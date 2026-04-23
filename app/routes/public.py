"""
Public (no-auth) routes. Slice A: /, /health. Slice B: sign-in flow.

- /                  Landing page + sign-in CTA.
- /health            Liveness probe for Docker HEALTHCHECK and Traefik loadbalancer.
- /api/v1/health     JSON twin.
- /sign-in           Redirects to Clerk's hosted AccountPortal sign-in page.
- /sign-in/callback  Verifies the Clerk session token, provisions the User,
                     sets our own __ds_session cookie, redirects to /facility/dashboard.
- /sign-out          Clears the cookie and redirects to /.

Auth flow (Slice B — single-page Clerk hosted flow + in-browser JS handoff):

Our /sign-in page includes a small inline script that loads `@clerk/clerk-js`
from Clerk's CDN, mounts nothing UI-wise, then immediately `window.location`s
to the Clerk AccountPortal sign-in URL. After sign-in, Clerk sends the browser
back to our /sign-in/callback with an active Clerk session. The callback page
then uses @clerk/clerk-js to fetch the short-lived session token via
`Clerk.session.getToken()` and POSTs it to /sign-in/exchange — which verifies,
provisions, and sets an HttpOnly `__ds_session` cookie.

This keeps the whole flow JS-light (one <script> tag, no build step) while
avoiding Clerk's tricky cross-domain cookie restrictions.

IMPLEMENTATION: Slice B.
"""

from __future__ import annotations

import base64
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.clerk_middleware import AuthError, verify_clerk_jwt
from app.auth.dependencies import SESSION_COOKIE_NAME
from app.auth.provisioning import NotOnAllowlist, provision_user
from app.config import get_settings
from app.db.database import get_session


def _clerk_frontend_host(publishable_key: str) -> str:
    """Decode the Clerk publishable key to extract its frontend-API host.

    Clerk keys are of the form `pk_test_<base64("<frontend_host>$")>`. The
    `$` is a terminator; we strip it. Returns e.g. 'clerk.foo.clerk.accounts.dev'
    for dev instances.
    """
    parts = publishable_key.split("_", 2)
    if len(parts) < 3:
        return ""
    try:
        padding = "=" * (-len(parts[2]) % 4)
        decoded = base64.b64decode(parts[2] + padding).decode("ascii", errors="ignore")
    except Exception:
        return ""
    return decoded.rstrip("$")


def _clerk_sign_in_portal_url(frontend_host: str) -> str:
    """Clerk's hosted AccountPortal sign-in URL for dev instances.

    Dev instance frontend host: `<slug>.clerk.accounts.dev`
    Account Portal host:        `<slug>.accounts.dev`
    """
    if not frontend_host:
        return ""
    host = frontend_host.removeprefix("clerk.")
    if host.endswith(".clerk.accounts.dev"):
        host = host[: -len(".clerk.accounts.dev")] + ".accounts.dev"
    return f"https://{host}/sign-in"


def _clerk_js_url(frontend_host: str) -> str:
    """The Clerk JS SDK served from the frontend host."""
    if not frontend_host:
        return ""
    return f"https://{frontend_host}/npm/@clerk/clerk-js@5/dist/clerk.browser.js"

router = APIRouter()
api_router = APIRouter(prefix="/api/v1")

SESSION_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 8  # 8 hours


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="landing.html",
        context={"page_title": "ds-meal", "user": None},
    )


@router.get("/health")
async def health_html():
    return JSONResponse({"status": "ok", "service": "ds-meal"})


@api_router.get("/health")
async def health_json():
    return JSONResponse({"status": "ok", "service": "ds-meal"})


# --- Sign-in flow --------------------------------------------------------


@router.get("/sign-in", response_class=HTMLResponse)
async def sign_in(request: Request):
    """Bootstrap page: load Clerk JS and trigger Google OAuth directly.

    We skip Clerk's hosted AccountPortal because its post-OAuth redirect
    ignores the ?redirect_url= query param on dev instances, landing users
    on accounts.dev/default-redirect instead of our /sign-in/callback.
    """
    settings = get_settings()
    pk = settings.CLERK_PUBLISHABLE_KEY
    host = _clerk_frontend_host(pk)
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="auth/sign_in.html",
        context={
            "page_title": "Sign in — ds-meal",
            "user": None,
            "publishable_key": pk,
            "clerk_js_url": _clerk_js_url(host),
            "clerk_configured": bool(pk and host),
        },
    )


@router.get("/sign-in/callback", response_class=HTMLResponse)
async def sign_in_callback(request: Request):
    """Client-side bounce: load Clerk JS, get session token, exchange for cookie."""
    settings = get_settings()
    pk = settings.CLERK_PUBLISHABLE_KEY
    host = _clerk_frontend_host(pk)
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="auth/callback.html",
        context={
            "page_title": "Signing in — ds-meal",
            "user": None,
            "publishable_key": pk,
            "clerk_js_url": _clerk_js_url(host),
        },
    )


@router.post("/sign-in/exchange")
async def sign_in_exchange(
    token: Annotated[str, Form()],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Verify the Clerk session JWT, provision the User, set our own cookie."""
    try:
        claims = verify_clerk_jwt(token)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    try:
        user = await provision_user(claims, session)
    except NotOnAllowlist as exc:
        # 403 rendered by the client-side handler as a friendly page.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"not_on_allowlist:{exc}",
        ) from exc

    response = JSONResponse(
        {
            "status": "signed_in",
            "user_id": user.id,
            "facility_id": user.facility_id,
            "redirect": "/facility/dashboard",
        }
    )
    # Slice B sets `secure=False` so tests over http:// can round-trip the cookie.
    # Prod toggles to True via a SECURE_COOKIES setting in Phase 2.
    response.set_cookie(
        SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/sign-out")
async def sign_out():
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


# Phase 2 Graduation: replace client-side JS handoff with a Clerk webhook-based
# server-side flow + proper OAuth PKCE; add CSRF tokens on /sign-in/exchange.
