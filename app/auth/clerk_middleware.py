"""
Clerk session-JWT verification via JWKS.

Clerk issues RS256-signed JWTs as session tokens. We fetch the JWKS once
(cached for TTL), look up the signing key by `kid` from the JWT header, and
verify the signature with PyJWT.

No Clerk SDK dependency — stdlib + PyJWT + httpx. Small, testable, auditable.

IMPLEMENTATION: Slice B.
Contract: PROTOCOL-APPLICATION-MATRIX §P15.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import jwt
from jwt import InvalidTokenError, PyJWKClient, PyJWKClientError

from app.config import get_settings


class AuthError(Exception):
    """Raised when a Clerk session JWT cannot be verified."""


@dataclass(frozen=True)
class ClerkClaims:
    """Minimal, strongly-typed projection of Clerk's JWT claims."""

    sub: str  # Clerk user id, e.g. "user_2abc..."
    email: str
    issued_at: int
    expires_at: int
    session_id: str | None = None
    raw: dict[str, Any] | None = None


# --- JWKS fetch + cache ---------------------------------------------------

_JWKS_TTL_SECONDS = 600  # 10 min
_jwks_client: PyJWKClient | None = None
_jwks_client_loaded_at: float = 0.0
_jwks_client_url: str | None = None  # track the URL it was built for


def _get_jwks_client() -> PyJWKClient:
    """Return a cached PyJWKClient bound to settings.CLERK_JWKS_URL."""
    global _jwks_client, _jwks_client_loaded_at, _jwks_client_url
    now = time.time()
    url = get_settings().CLERK_JWKS_URL
    if not url:
        raise AuthError("CLERK_JWKS_URL is not configured")

    expired = (now - _jwks_client_loaded_at) > _JWKS_TTL_SECONDS
    mismatched = _jwks_client_url != url
    if _jwks_client is None or expired or mismatched:
        _jwks_client = PyJWKClient(url, cache_keys=True, lifespan=_JWKS_TTL_SECONDS)
        _jwks_client_loaded_at = now
        _jwks_client_url = url
    return _jwks_client


def reset_jwks_cache() -> None:
    """Test helper — drop the cached JWKS client."""
    global _jwks_client, _jwks_client_loaded_at, _jwks_client_url
    _jwks_client = None
    _jwks_client_loaded_at = 0.0
    _jwks_client_url = None


# --- Token verification ---------------------------------------------------


def verify_clerk_jwt(token: str, *, audience: str | None = None) -> ClerkClaims:
    """
    Verify a Clerk session JWT. Raises AuthError on any failure.

    Steps:
      1. Resolve the signing key via JWKS (using the `kid` in the token header).
      2. Validate RS256 signature.
      3. Enforce `exp` and `iat`.
      4. Extract `sub`, `email`, `sid`.

    `audience` is optional — Clerk's default session tokens omit `aud`; some
    custom JWT templates set it. When provided it is enforced.
    """
    if not token or not isinstance(token, str):
        raise AuthError("missing_token")

    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
    except (PyJWKClientError, InvalidTokenError) as exc:
        raise AuthError(f"signing_key_lookup_failed: {exc}") from exc

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience,
            options={"require": ["exp", "iat"]},
        )
    except InvalidTokenError as exc:
        raise AuthError(f"jwt_verification_failed: {exc}") from exc

    email = _extract_email(claims)
    if not email:
        raise AuthError("missing_email_claim")

    return ClerkClaims(
        sub=claims["sub"],
        email=email.lower().strip(),
        issued_at=claims["iat"],
        expires_at=claims["exp"],
        session_id=claims.get("sid"),
        raw=claims,
    )


def _extract_email(claims: dict[str, Any]) -> str | None:
    """Walk common Clerk JWT-template shapes to locate the user's email."""
    for key in ("email", "primary_email_address", "primary_email"):
        value = claims.get(key)
        if isinstance(value, str) and "@" in value:
            return value

    for path in (("user", "email"), ("metadata", "email"), ("user", "primary_email_address")):
        node: Any = claims
        for step in path:
            if not isinstance(node, dict) or step not in node:
                node = None
                break
            node = node[step]
        if isinstance(node, str) and "@" in node:
            return node

    return None


# Phase 2 Graduation: swap the PyJWKClient in-process cache for a Redis-backed cache
# shared across ASGI workers; add org-scoped claim extraction (org_id, org_role) when
# Clerk Organizations are enabled for multi-tenant RBAC.
