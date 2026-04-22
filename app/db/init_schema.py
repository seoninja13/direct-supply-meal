"""
PSEUDOCODE:
1. One-line summary of module purpose.
   - Startup schema bootstrap: SQLModel.metadata.create_all + agent_trace table (Karpathy Layer 1).
2. Ordered steps.
   a. Import every model module so their tables register into SQLModel.metadata.
   b. Declare the AgentTrace SQLModel — the Karpathy auto-research Layer 1 observability table
      per docs/workflows/KARPATHY-AUTO-RESEARCH-WORKFLOW.md.
   c. On app startup, call init_schema(engine) which runs metadata.create_all via a sync wrapper
      over the async engine, then creates the composite index idx_agent_trace_name_ts.
   d. In Phase 1 we use create_all (no migrations). Phase 2 adds Alembic.
3. Inputs / Outputs.
   - Inputs: the AsyncEngine produced by app.db.database.get_engine().
   - Outputs: all tables materialized in the target DB + agent_trace index.
4. Side effects.
   - Writes to the database schema. Idempotent — create_all is a no-op on existing tables.

IMPLEMENTATION: Phase 4 — see functions below.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

# PSEUDO: Re-import every model so metadata is populated before create_all runs.
#   - Facility / DeliveryWindow enum
#   - User
#   - Resident + DietaryFlag + ResidentDietaryFlag
#   - Recipe + Ingredient + RecipeIngredient
#   - MealPlan + MealPlanSlot
#   - Order + OrderLine + OrderStatusEvent
from app.models import facility as _facility  # noqa: F401
from app.models import user as _user  # noqa: F401
from app.models import resident as _resident  # noqa: F401
from app.models import recipe as _recipe  # noqa: F401
from app.models import meal_plan as _meal_plan  # noqa: F401
from app.models import order as _order  # noqa: F401


class AgentTrace(SQLModel, table=True):
    # PSEUDO: Karpathy Layer 1 trace row — one per agent invocation.
    #   - id: PK.
    #   - ts: UTC timestamp of the invocation (indexed via composite idx below).
    #   - agent_name: driver name ("menu_planner", "nl_ordering", ...).
    #   - query_text: user-visible query passed to ClaudeSDKClient / query().
    #   - tool_calls_json: JSON list of {name, args, result_summary, duration_ms}.
    #   - outcome: terminal string ("success" | "error" | "timeout" | "guarded_fail").
    #   - confidence_score: float 0..1 from the agent or tool layer (nullable).
    #   - latency_ms: end-to-end wall-clock latency (int).
    #   - cost_cents: computed cost in cents (Claude Agent SDK billing).
    #   - notes: free-form string (optional).
    __tablename__ = "agent_trace"

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=datetime.utcnow, index=True)
    agent_name: str = Field(index=True)
    query_text: str
    tool_calls_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    outcome: str
    confidence_score: Optional[float] = Field(default=None)
    latency_ms: int
    cost_cents: int
    notes: Optional[str] = Field(default=None)


# PSEUDO: Composite index for the most common Layer 1 query shape:
#   "latest N rows for agent_name=X ordered by ts desc".
idx_agent_trace_name_ts = Index(
    "idx_agent_trace_name_ts",
    AgentTrace.__table__.c.agent_name,
    AgentTrace.__table__.c.ts,
)


async def init_schema(engine: AsyncEngine) -> None:
    # PSEUDO: Bootstrap schema at app startup.
    #   1. async with engine.begin() as conn:
    #        await conn.run_sync(SQLModel.metadata.create_all)
    #   2. create_all is idempotent; no-op on existing DB.
    #   3. Indexes declared on Column(index=True) are created automatically; the explicit composite
    #      idx_agent_trace_name_ts above is included in metadata and created in the same call.
    #   4. Returns None; raises SQLAlchemyError on failure (caller logs + aborts startup).
    raise NotImplementedError


# Phase 2 Graduation: replace create_all with Alembic migrations; add agent_trace retention /
# archival job (>30 days → cold storage); add a materialized view for daily cost roll-ups.
