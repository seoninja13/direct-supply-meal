"""
PSEUDOCODE:
1. Import every model module so SQLModel.metadata is fully populated.
2. Declare AgentTrace (Karpathy Layer 1) SQLModel table.
3. init_schema() runs `metadata.create_all` via the async engine; idempotent.
4. Composite index idx_agent_trace_name_ts is part of metadata via `sa_column` — created automatically.

IMPLEMENTATION: Phase 4.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.db.database import get_engine

# Ensure every model module registers its tables into SQLModel.metadata.
from app.models import facility as _facility  # noqa: F401
from app.models import meal_plan as _meal_plan  # noqa: F401
from app.models import order as _order  # noqa: F401
from app.models import recipe as _recipe  # noqa: F401
from app.models import resident as _resident  # noqa: F401
from app.models import usda_food as _usda_food  # noqa: F401
from app.models import user as _user  # noqa: F401


class AgentTrace(SQLModel, table=True):
    """Karpathy Layer 1 trace row — one per agent invocation. See KARPATHY-AUTO-RESEARCH §3."""

    __tablename__ = "agent_trace"

    id: int | None = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=datetime.utcnow, index=True)
    agent_name: str = Field(index=True)
    query_text: str
    tool_calls_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    outcome: str
    confidence_score: float | None = Field(default=None)
    latency_ms: int
    cost_cents: int
    notes: str | None = Field(default=None)


async def init_schema() -> None:
    """Create all tables idempotently. Called from app lifespan on startup."""
    engine = get_engine()

    # Ensure SQLite file's parent directory exists (bind-mounted at /app/data in prod).
    url = str(engine.url)
    if url.startswith("sqlite+aiosqlite:////"):
        db_path = Path("/" + url.split("sqlite+aiosqlite:////", 1)[1])
        db_path.parent.mkdir(parents=True, exist_ok=True)
    elif url.startswith("sqlite+aiosqlite:///"):
        # Relative path form — resolve against CWD.
        db_path = Path(url.split("sqlite+aiosqlite:///", 1)[1])
        db_path.parent.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


# Phase 2 Graduation: replace create_all with Alembic migrations; add agent_trace retention job.
