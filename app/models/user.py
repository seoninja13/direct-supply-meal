"""
PSEUDOCODE:
1. One-line summary of module purpose.
   - User SQLModel bound to a Facility via clerk_user_id — provisioned on Clerk sign-in (J2).
2. Ordered steps.
   a. Declare User SQLModel with table=True.
   b. Fields: id PK, clerk_user_id UNIQUE, email UNIQUE, facility_id FK, role, created_at.
   c. Provisioning middleware INSERTs a row on first successful sign-in after allowlist match.
3. Inputs / Outputs.
   - Inputs: Clerk JWT claims (sub → clerk_user_id, email) + Facility match (admin_email).
   - Outputs: User row referenced by MealPlan.created_by_user_id and Order.placed_by_user_id.
4. Side effects.
   - None at model level. Provisioning write happens in auth/dependencies.py (Phase 4).

IMPLEMENTATION: Phase 4 — see functions below.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    # PSEUDO: User table — identity + tenancy binding.
    #   - id: PK.
    #   - clerk_user_id: Clerk's opaque subject identifier (unique; primary lookup on each request).
    #   - email: unique email (secondary lookup + allowlist match source).
    #   - facility_id: FK to facility.id — every user belongs to exactly one facility in Phase 1.
    #   - role: string role ("admin", "dietitian", "kitchen"). Phase 1 treats admin as canonical.
    #   - created_at: provisioning timestamp (UTC, set on INSERT).
    __tablename__ = "user"

    id: Optional[int] = Field(default=None, primary_key=True)
    clerk_user_id: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    facility_id: int = Field(foreign_key="facility.id", index=True)
    role: str = Field(default="admin")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Phase 2 Graduation: replace free-string role with an RBAC role table + many-to-many role assignment;
# add last_seen_at, soft-delete (deleted_at), and per-facility scoping for multi-tenant admin mode.
