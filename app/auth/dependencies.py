"""
FastAPI dependency helpers for Clerk-authenticated routes.

- require_login(): verify Clerk JWT from cookie/header, load User row, return CurrentUser.
- require_facility_access(): raise 403 when user.facility_id != resource.facility_id.

IMPLEMENTATION: Slice B.
Contract: PROTOCOL-APPLICATION-MATRIX §P15.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.clerk_middleware import AuthError, verify_clerk_jwt
from app.db.database import get_session
from app.models.user import User

SESSION_COOKIE_NAME = "__session"  # Clerk's default


@dataclass(frozen=True)
class CurrentUser:
    """Typed projection returned to route handlers."""

    user_id: int
    clerk_user_id: str
    email: str
    facility_id: int


def _extract_token(request: Request) -> str:
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()

    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie:
        return cookie

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="missing_token",
    )


async def require_login(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CurrentUser:
    """FastAPI dependency: verify Clerk JWT → load User → return CurrentUser."""
    token = _extract_token(request)

    try:
        claims = verify_clerk_jwt(token)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid_token: {exc}",
        ) from exc

    result = await session.execute(
        select(User).where(User.clerk_user_id == claims.sub)
    )
    user_row = result.scalar_one_or_none()

    if user_row is None:
        # Either the user hasn't signed in yet, OR their email isn't on a
        # Facility.admin_email allowlist (provisioning rejects unknown emails).
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not_provisioned",
        )

    return CurrentUser(
        user_id=user_row.id,
        clerk_user_id=user_row.clerk_user_id,
        email=user_row.email,
        facility_id=user_row.facility_id,
    )


def require_facility_access(resource_facility_id: int, user: CurrentUser) -> CurrentUser:
    """Tenancy guard: 403 when the resource belongs to a different facility."""
    if user.facility_id != resource_facility_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="cross_facility",
        )
    return user


# Phase 2 Graduation: add require_role(role: str) factory extending require_login with
# a role check. Used by multi-tenant RBAC when >1 admin per facility or >1 facility per admin.
