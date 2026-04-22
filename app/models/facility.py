"""
PSEUDOCODE:
1. One-line summary of module purpose.
   - Facility SQLModel (tenancy root) and the DeliveryWindow slot enum per DOMAIN-WORKFLOW Section 2.
2. Ordered steps.
   a. Declare FacilityType enum (AL | SNF | MC | IL).
   b. Declare DeliveryWindow enum (morning_6_8 | midday_11_1 | evening_4_6).
   c. Declare Facility SQLModel with table=True — id, name, type, bed_count, admin_email.
   d. admin_email is nullable (only one facility in seed is admin-bound per Section 8).
3. Inputs / Outputs.
   - Inputs: ORM fields populated by seed script / Clerk provisioning flow.
   - Outputs: Facility rows keyed by id; referenced by FK from User, Resident, MealPlan, Order.
4. Side effects.
   - None. Table definition only. Metadata registered into SQLModel.metadata on import.

IMPLEMENTATION: Phase 4 — see functions below.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class FacilityType(str, Enum):
    # PSEUDO: Canonical facility categories used across dashboards, roll-ups, dietary defaults.
    #   - AL: Assisted Living.
    #   - SNF: Skilled Nursing Facility.
    #   - MC: Memory Care.
    #   - IL: Independent Living.
    AL = "AL"
    SNF = "SNF"
    MC = "MC"
    IL = "IL"


class DeliveryWindow(str, Enum):
    # PSEUDO: Fixed delivery slot catalog referenced by Order.delivery_window_slot.
    #   - morning_6_8: 06:00–08:00 breakfast window.
    #   - midday_11_1: 11:00–13:00 lunch window.
    #   - evening_4_6: 16:00–18:00 dinner window.
    MORNING_6_8 = "morning_6_8"
    MIDDAY_11_1 = "midday_11_1"
    EVENING_4_6 = "evening_4_6"


class Facility(SQLModel, table=True):
    # PSEUDO: Facility table — tenancy root.
    #   - id: PK.
    #   - name: human-readable facility name ("Riverside SNF").
    #   - type: FacilityType enum value stored as string.
    #   - bed_count: licensed bed capacity (planning signal for compliance roll-ups).
    #   - admin_email: optional allowlist anchor matched during Clerk provisioning (J2).
    __tablename__ = "facility"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    type: FacilityType
    bed_count: int
    admin_email: Optional[str] = Field(default=None, index=True, unique=True)


# Phase 2 Graduation: add per-facility RBAC role tables + multi-admin allowlist; split DeliveryWindow
# into a proper table with per-facility overrides once more than one admin onboards.
