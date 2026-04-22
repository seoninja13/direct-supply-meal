"""
agents/observability.py — Karpathy Auto-Research Layer 1 trace ingestion.

`record_outcome(trace_row)` is called from every agent driver's `finally` block.
Writes one row to the SQLite `agent_trace` table AND one JSONL line to
`logs/agent_trace.jsonl`. Optionally dumps full payload JSON to
`logs/agent_payloads/{trace_id}.json`.

Design rules (from KARPATHY-AUTO-RESEARCH §3/§4):
- NEVER fails in a way that breaks the agent — all errors logged + swallowed.
- NEVER clusters, embeds, or calls LLMs — pure ingestion.
- Function body stays short; Layer 2 clustering lives in `wiki/compiler.py`.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from app.db.database import get_session
from app.db.init_schema import AgentTrace

logger = logging.getLogger(__name__)

TRACE_FIELDS: tuple[str, ...] = (
    "ts",
    "agent_name",
    "query_text",
    "tool_calls_json",
    "outcome",
    "confidence_score",
    "latency_ms",
    "cost_cents",
    "notes",
)

JSONL_PATH = Path("logs/agent_trace.jsonl")
PAYLOADS_DIR = Path("logs/agent_payloads")


def _normalize_trace_row(trace_row: dict[str, Any]) -> dict[str, Any]:
    """Fill missing fields with safe defaults."""
    normalized: dict[str, Any] = {}
    for field in TRACE_FIELDS:
        value = trace_row.get(field)
        if field == "ts" and value is None:
            value = datetime.utcnow()
        elif field == "agent_name" and value is None:
            value = "unknown"
        elif field == "query_text" and value is None:
            value = ""
        elif field == "tool_calls_json" and value is None:
            value = []
        elif field == "outcome" and value is None:
            value = "unknown"
        elif field == "latency_ms" and value is None:
            value = 0
        elif field == "cost_cents" and value is None:
            value = 0
        normalized[field] = value
    return normalized


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    """Append one JSON line. Creates parent dir if missing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = dict(row)
    if isinstance(serializable.get("ts"), datetime):
        serializable["ts"] = serializable["ts"].isoformat()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(serializable, default=str) + "\n")


async def record_outcome(
    trace_row: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> int:
    """Persist one agent invocation outcome to SQLite + JSONL.

    Args:
        trace_row: dict with the canonical agent_trace fields (TRACE_FIELDS).
                   Missing fields get filled with safe defaults.
        payload: optional full request/response payload for deep post-mortems.

    Returns:
        int — the newly assigned agent_trace.id, or -1 on any failure.

    This function MUST NOT break the caller's finally block. All exceptions
    are caught, logged, and swallowed with a -1 return.
    """
    try:
        normalized = _normalize_trace_row(trace_row)

        trace_id: int | None = None
        async for session in get_session():
            trace = AgentTrace(
                ts=normalized["ts"],
                agent_name=normalized["agent_name"],
                query_text=normalized["query_text"],
                tool_calls_json=normalized["tool_calls_json"],
                outcome=normalized["outcome"],
                confidence_score=normalized.get("confidence_score"),
                latency_ms=normalized["latency_ms"],
                cost_cents=normalized["cost_cents"],
                notes=normalized.get("notes"),
            )
            session.add(trace)
            await session.commit()
            await session.refresh(trace)
            trace_id = trace.id
            break

        if trace_id is None:
            return -1

        try:
            _append_jsonl(JSONL_PATH, {"id": trace_id, **normalized})
        except Exception:
            logger.exception("record_outcome: JSONL append failed (non-fatal)")

        if payload is not None:
            try:
                PAYLOADS_DIR.mkdir(parents=True, exist_ok=True)
                (PAYLOADS_DIR / f"{trace_id}.json").write_text(
                    json.dumps(payload, default=str, indent=2),
                    encoding="utf-8",
                )
            except Exception:
                logger.exception("record_outcome: payload write failed (non-fatal)")

        return trace_id

    except Exception:
        logger.exception("record_outcome: trace insert failed — swallowing")
        return -1


# Phase 2 Graduation: record_outcome() grows an embedding step — MiniLM 384-dim
# vector of query_text serialized to a new agent_trace.embedding BLOB column.
# Seam is this function's body; signature stays identical.
