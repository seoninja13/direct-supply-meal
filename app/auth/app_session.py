"""
App-issued session tokens (Phase 1).

After Clerk authenticates a user, /sign-in/exchange verifies the Clerk JWT
once and then mints this app-side token. Per-request auth verifies the
app-side token only — no Clerk round-trip, no dependence on Clerk's short
(~60s) session-JWT TTL.

Signed HS256 with CLERK_SECRET_KEY (already configured; avoids adding a
second secret). Payload carries the Clerk `sub` so we can still look up
the provisioned User row by clerk_user_id.

Phase 2 Graduation: move to a dedicated APP_SESSION_SECRET + server-side
session store keyed by an opaque cookie value (no JWT in the cookie).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import jwt
from jwt import InvalidTokenError

from app.auth.clerk_middleware import AuthError
from app.config import get_settings

APP_SESSION_TTL_SECONDS = 60 * 60  # 1 hour
_ALG = "HS256"
_ISSUER = "ds-meal"


@dataclass(frozen=True)
class AppSession:
    sub: str
    email: str
    issued_at: int
    expires_at: int


def mint_app_session(sub: str, email: str) -> str:
    secret = get_settings().CLERK_SECRET_KEY
    if not secret:
        raise AuthError("APP_SESSION_SECRET missing (set CLERK_SECRET_KEY)")
    now = int(time.time())
    payload = {
        "iss": _ISSUER,
        "sub": sub,
        "email": email,
        "iat": now,
        "exp": now + APP_SESSION_TTL_SECONDS,
    }
    return jwt.encode(payload, secret, algorithm=_ALG)


def verify_app_session(token: str) -> AppSession:
    if not token or not isinstance(token, str):
        raise AuthError("missing_token")
    secret = get_settings().CLERK_SECRET_KEY
    if not secret:
        raise AuthError("APP_SESSION_SECRET missing (set CLERK_SECRET_KEY)")
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[_ALG],
            issuer=_ISSUER,
            options={"require": ["exp", "iat", "sub", "email"]},
        )
    except InvalidTokenError as exc:
        raise AuthError(f"app_session_invalid: {exc}") from exc
    return AppSession(
        sub=claims["sub"],
        email=claims["email"],
        issued_at=claims["iat"],
        expires_at=claims["exp"],
    )
