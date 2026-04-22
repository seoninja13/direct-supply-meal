"""
First-sign-in user provisioning.

Flow: /sign-in/callback verifies the Clerk JWT, then calls provision_user(claims).
- If a User row exists for `claims.sub` → return it (idempotent re-sign-in).
- Else match `Facility.admin_email` to `claims.email`.
    - No match → raise NotOnAllowlist (route maps to 403).
    - Match → INSERT the User row and return it.

IMPLEMENTATION: Slice B.
Contract: PROTOCOL-APPLICATION-MATRIX §P15.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.clerk_middleware import ClerkClaims
from app.models.facility import Facility
from app.models.user import User


class NotOnAllowlist(Exception):
    """The sign-in email does not match any Facility.admin_email row."""


async def provision_user(claims: ClerkClaims, session: AsyncSession) -> User:
    """Idempotent provisioning. Returns the User row bound to a facility.

    Three cases:
      1. User row already exists for `claims.sub` — return it.
      2. A placeholder row exists for `claims.email` (seeded with
         clerk_user_id='__unprovisioned__') — upgrade it in place.
      3. No row — match Facility.admin_email and INSERT a new user,
         or raise NotOnAllowlist.
    """
    # Case 1: already provisioned for this Clerk user.
    by_sub = await session.execute(select(User).where(User.clerk_user_id == claims.sub))
    row = by_sub.scalar_one_or_none()
    if row is not None:
        if row.email != claims.email:
            row.email = claims.email
            await session.commit()
            await session.refresh(row)
        return row

    # Case 2: seed placeholder on the allowlisted email.
    by_email = await session.execute(select(User).where(User.email == claims.email))
    placeholder = by_email.scalar_one_or_none()
    if placeholder is not None:
        placeholder.clerk_user_id = claims.sub
        await session.commit()
        await session.refresh(placeholder)
        return placeholder

    # Case 3: fresh provisioning path. Must match Facility.admin_email.
    facility_lookup = await session.execute(
        select(Facility).where(Facility.admin_email == claims.email)
    )
    facility = facility_lookup.scalar_one_or_none()
    if facility is None:
        raise NotOnAllowlist(claims.email)

    user = User(
        clerk_user_id=claims.sub,
        email=claims.email,
        facility_id=facility.id,
        role="admin",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


# Phase 2 Graduation: move to an Inngest-handled Clerk webhook queue for durable provisioning;
# extend provision_user() to honour org-scoped roles when Clerk Organizations replace the
# single-admin allowlist; dedicated provisioning log file.
